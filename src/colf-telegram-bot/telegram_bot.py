import logging
import os
from datetime import date

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from expense_card import (
    FIELD_PROMPTS,
    apply_field_value,
    back_only_keyboard,
    category_keyboard,
    format_card,
    main_keyboard,
)
from invoice_card import (
    INV_FIELD_PROMPTS,
    format_invoice_card,
    invoice_back_keyboard,
    invoice_main_keyboard,
)
from notification_ingest import (
    NotificationIngestServer,
    build_parse_notification_request,
    create_ingest_server_from_env,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        self.api_base_url = os.getenv("API_BASE_URL")
        self.notification_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        # L'inoltro delle notifiche bancarie si accende e si spegne dall'app
        # Android ("Abilita inoltro"): qui non c'è un secondo interruttore.
        self.ingest_server: NotificationIngestServer | None = None
        self.application = (
            Application.builder()
            .token(self.bot_token)
            .post_init(self._post_init)
            .post_shutdown(self._post_shutdown)
            .build()
        )
        self._setup_handlers()

    async def _post_init(self, application: Application) -> None:
        """Eseguito da `run_polling` dopo l'inizializzazione: avvia il server
        di ingest notifiche se INGEST_TOKEN/TELEGRAM_CHAT_ID sono configurati."""
        logger.info("Bot is running. Press Ctrl+C to stop.")
        self.ingest_server = create_ingest_server_from_env(self)
        if self.ingest_server is not None:
            await self.ingest_server.start()

    async def _post_shutdown(self, application: Application) -> None:
        """Eseguito da `run_polling` in fase di spegnimento: ferma il server
        di ingest notifiche, se era stato avviato."""
        if self.ingest_server is not None:
            await self.ingest_server.stop()
            self.ingest_server = None

    def _setup_handlers(self):
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(CommandHandler("fattura", self.handle_fattura))
        self.application.add_handler(CommandHandler("clienti", self.handle_clienti))
        self.application.add_handler(CommandHandler("scadenze", self.handle_scadenze))
        self.application.add_handler(CommandHandler("stato", self.handle_stato))

    @staticmethod
    def _clear(context: ContextTypes.DEFAULT_TYPE) -> None:
        for key in (
            "draft",
            "categories",
            "card_message_id",
            "awaiting_field",
            "from_notification",
            "needs_category_refresh",
        ):
            context.chat_data.pop(key, None)

    @staticmethod
    def _clear_invoice(context: ContextTypes.DEFAULT_TYPE) -> None:
        for key in ("invoice_draft", "invoice_card_message_id", "invoice_awaiting_field"):
            context.chat_data.pop(key, None)

    # ── Expense handlers (unchanged) ──────────────────────────────────────────

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        text = update.message.text
        chat_data = context.chat_data

        if chat_data.get("invoice_awaiting_field"):
            await self._apply_invoice_field(update, context, text)
            return

        if chat_data.get("awaiting_field"):
            await self._apply_field_value(update, context, text)
            return

        if chat_data.get("draft"):
            await update.message.reply_text(
                "⏳ Conferma o annulla prima la spesa in sospeso."
            )
            return

        if chat_data.get("invoice_draft"):
            await update.message.reply_text(
                "⏳ Conferma o annulla prima la fattura in sospeso."
            )
            return

        await self._start_draft(update, context, text)

    async def _replace_placeholder(self, placeholder, update, text, reply_markup=None):
        """Sostituisce il messaggio placeholder con uno nuovo.

        Modificare un messaggio (edit) non genera una notifica push su Telegram:
        per far arrivare l'avviso sul telefono il risultato va inviato come nuovo
        messaggio. Cancella il placeholder e invia una reply fresca.
        """
        try:
            await placeholder.delete()
        except Exception as delete_error:
            logger.debug("Could not delete placeholder message: %s", delete_error)
        return await update.message.reply_text(text, reply_markup=reply_markup)

    async def _start_draft(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        thinking = await update.message.reply_text("Sto elaborando… 🤔")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/agents/expenses/parse",
                    json={"message": text},
                    timeout=120.0,
                )
            response.raise_for_status()
            result = response.json()
        except Exception as error:
            logger.error("Parse request failed: %s", error)
            await self._replace_placeholder(
                thinking, update, "❌ Errore nel processare il messaggio. Riprova."
            )
            return

        if not result.get("success"):
            logger.error("Parse error: %s", result.get("error"))
            await self._replace_placeholder(
                thinking, update, "❌ Errore nel processare il messaggio. Riprova."
            )
            return

        context.chat_data["draft"] = result["draft"]
        context.chat_data["categories"] = result["categories"]
        card = await self._replace_placeholder(
            thinking,
            update,
            format_card(result["draft"]),
            reply_markup=main_keyboard(bool(result["draft"].get("participants"))),
        )
        context.chat_data["card_message_id"] = card.message_id

    async def _apply_field_value(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        field = context.chat_data["awaiting_field"]
        draft = context.chat_data["draft"]

        error = apply_field_value(draft, field, text)
        try:
            await update.message.delete()
        except Exception as delete_error:
            logger.debug("Could not delete user message: %s", delete_error)

        if error is not None:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=context.chat_data["card_message_id"],
                text=f"{format_card(draft)}\n\n{FIELD_PROMPTS[field]}\n\n{error}",
                reply_markup=back_only_keyboard(),
            )
            return

        context.chat_data["awaiting_field"] = None

        # Spese da notifica bancaria senza descrizione riconosciuta: una volta
        # che l'utente la scrive, ricategorizza. Il flusso testuale normale non
        # imposta mai questo flag, quindi il suo comportamento non cambia.
        if field == "description" and context.chat_data.pop(
            "needs_category_refresh", False
        ):
            await self._refresh_category(draft)

        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=context.chat_data["card_message_id"],
            text=format_card(draft),
            reply_markup=main_keyboard(bool(draft.get("participants"))),
        )

    async def _refresh_category(self, draft: dict) -> None:
        """Ricategorizza la spesa dopo che l'utente ha inserito la descrizione
        mancante da una notifica bancaria. Se la chiamata fallisce, logga e
        lascia la categoria di fallback: non deve rompere il flusso."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/agents/expenses/categorize",
                    json={"description": draft["description"]},
                    timeout=60.0,
                )
            response.raise_for_status()
            result = response.json()
        except Exception as error:
            logger.error("Categorize request failed: %s", error)
            return

        if result.get("success") and result.get("category"):
            draft["category"] = result["category"]
        else:
            logger.error("Categorize error: %s", result.get("error"))

    # ── Bank notification ingest ────────────────────────────────────────────────

    async def handle_bank_notification(self, payload: dict) -> str:
        """Gestisce una notifica bancaria già validata dal server di ingest:
        chiama l'API di parsing e manda la scheda spesa in chat, riusando
        esattamente `format_card`/`main_keyboard` del flusso testuale.

        Ritorna "ok", "busy" (c'è già un draft spesa/fattura in sospeso) o
        "error" (l'API di parsing ha fallito). Non solleva eccezioni per gli
        errori attesi dell'API: solo un errore imprevisto si propaga.
        """
        chat_id = int(self.notification_chat_id)
        chat_data = self.application.chat_data[chat_id]

        if chat_data.get("draft") or chat_data.get("invoice_draft"):
            title = payload.get("title") or ""
            text = payload.get("text") or ""
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=(
                    "⚠️ Notifica di spesa ricevuta ma c'è già qualcosa in sospeso:\n"
                    f"{title} — {text}"
                ),
            )
            return "busy"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/agents/expenses/parse-notification",
                    json=build_parse_notification_request(payload),
                    timeout=120.0,
                )
            response.raise_for_status()
            result = response.json()
        except Exception as error:
            logger.error("Parse-notification request failed: %s", error)
            return "error"

        if not result.get("success"):
            logger.error("Parse-notification error: %s", result.get("error"))
            return "error"

        draft = result["draft"]
        chat_data["draft"] = draft
        chat_data["categories"] = result["categories"]
        chat_data["from_notification"] = True

        if result.get("needs_description"):
            chat_data["awaiting_field"] = "description"
            chat_data["needs_category_refresh"] = True
            text = (
                "⚠️ Non sono riuscito a capire la descrizione dalla notifica.\n\n"
                f"{format_card(draft)}\n\n{FIELD_PROMPTS['description']}"
            )
            card = await self.application.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=back_only_keyboard()
            )
        else:
            card = await self.application.bot.send_message(
                chat_id=chat_id,
                text=format_card(draft),
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )

        chat_data["card_message_id"] = card.message_id
        return "ok"

    # ── Invoice command handlers ───────────────────────────────────────────────

    async def handle_fattura(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        args = context.args
        if not args:
            await update.message.reply_text(
                "Usa: /fattura <nome cliente>\nEs: /fattura Acme"
            )
            return

        query = " ".join(args)
        thinking = await update.message.reply_text(f"Cerco cliente '{query}'… 🔍")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/invoices/parse",
                    json={"query": query},
                    timeout=30.0,
                )
            response.raise_for_status()
            result = response.json()
        except Exception as error:
            logger.error("Invoice parse failed: %s", error)
            await self._replace_placeholder(
                thinking, update, "❌ Errore nella ricerca del cliente. Riprova."
            )
            return

        if not result.get("success"):
            await self._replace_placeholder(
                thinking, update, f"❌ {result.get('error', 'Cliente non trovato.')}"
            )
            return

        context.chat_data["invoice_draft"] = result["draft"]
        card = await self._replace_placeholder(
            thinking,
            update,
            format_invoice_card(result["draft"]),
            reply_markup=invoice_main_keyboard(),
        )
        context.chat_data["invoice_card_message_id"] = card.message_id

    async def handle_clienti(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/api/clients",
                    params={"active_only": "true"},
                    timeout=10.0,
                )
            response.raise_for_status()
            clients = response.json()
        except Exception as error:
            logger.error("Clients list failed: %s", error)
            await update.message.reply_text("❌ Errore nel recuperare i clienti.")
            return

        if not clients:
            await update.message.reply_text("Nessun cliente attivo registrato.")
            return

        lines = ["👥 Clienti attivi:\n"]
        for c in clients:
            lines.append(f"• {c['ragione_sociale']} — P.IVA {c['piva']}")
        await update.message.reply_text("\n".join(lines))

    async def handle_scadenze(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/api/invoices/expiring",
                    timeout=10.0,
                )
            response.raise_for_status()
            invoices = response.json()
        except Exception as error:
            logger.error("Expiring invoices failed: %s", error)
            await update.message.reply_text("❌ Errore nel recuperare le scadenze.")
            return

        if not invoices:
            await update.message.reply_text("Nessuna fattura in scadenza nei prossimi 7 giorni.")
            return

        lines = ["⏰ Fatture in scadenza:\n"]
        for inv in invoices:
            lines.append(
                f"• n.{inv['numero']}/{inv['anno']} — {inv['ragione_sociale']} — "
                f"€ {inv['totale']} — scade {inv['data_scadenza']} — {inv['stato']}"
            )
        await update.message.reply_text("\n".join(lines))

    async def handle_stato(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text(
                "Usa: /stato <numero fattura>\nEs: /stato 73"
            )
            return

        numero = int(args[0])
        anno = date.today().year
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/api/invoices/{numero}",
                    params={"anno": anno},
                    timeout=10.0,
                )
            response.raise_for_status()
            inv = response.json()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                await update.message.reply_text(
                    f"Fattura n.{numero}/{anno} non trovata."
                )
            else:
                await update.message.reply_text("❌ Errore nel recuperare la fattura.")
            return
        except Exception as error:
            logger.error("Invoice status failed: %s", error)
            await update.message.reply_text("❌ Errore nel recuperare la fattura.")
            return

        await update.message.reply_text(
            f"📄 Fattura n.{inv['numero']}/{inv['anno']}\n"
            f"Cliente: {inv['ragione_sociale']}\n"
            f"Descrizione: {inv['descrizione']}\n"
            f"Importo: € {inv['importo']} + bollo\n"
            f"Totale: € {inv['totale']}\n"
            f"Emissione: {inv['data_emissione']}\n"
            f"Scadenza: {inv['data_scadenza']}\n"
            f"Stato: {inv['stato']}\n"
            f"Progressivo: {inv['progressivo_invio']}"
        )

    # ── Invoice field editing ─────────────────────────────────────────────────

    async def _apply_invoice_field(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        field = context.chat_data["invoice_awaiting_field"]
        draft = context.chat_data["invoice_draft"]
        error = None

        if field == "amount":
            draft["importo"] = text.strip().replace(",", ".")
        elif field == "description":
            draft["descrizione"] = text.strip()
        elif field == "date":
            stripped = text.strip()
            try:
                date.fromisoformat(stripped)
                draft["data_emissione"] = stripped
            except ValueError:
                error = "⚠️ Formato non valido. Usa YYYY-MM-DD (es. 2026-06-01)."
        elif field == "giorni":
            if not text.strip().isdigit():
                error = "⚠️ Inserisci un numero intero (es. 30)."
            else:
                draft["giorni_pagamento"] = int(text.strip())

        try:
            await update.message.delete()
        except Exception as delete_error:
            logger.debug("Could not delete user message: %s", delete_error)

        if error is not None:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=context.chat_data["invoice_card_message_id"],
                text=f"{format_invoice_card(draft)}\n\n{INV_FIELD_PROMPTS[field]}\n\n{error}",
                reply_markup=invoice_back_keyboard(),
            )
            return

        context.chat_data["invoice_awaiting_field"] = None
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=context.chat_data["invoice_card_message_id"],
            text=format_invoice_card(draft),
            reply_markup=invoice_main_keyboard(),
        )

    # ── Callback router ───────────────────────────────────────────────────────

    async def handle_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        data = query.data

        if data.startswith("inv_"):
            await self._handle_invoice_callback(update, context)
            return

        # ── Expense callbacks (unchanged) ──────────────────────────────────
        chat_data = context.chat_data

        if not chat_data.get("draft"):
            await query.answer("Questa spesa non è più in sospeso.", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=None)
            return

        await query.answer()
        chat_data["awaiting_field"] = None
        draft = chat_data["draft"]

        if data == "confirm":
            await self._commit(update, context)
        elif data == "cancel":
            self._clear(context)
            await query.edit_message_text("Spesa annullata.")
        elif data == "edit:category":
            await query.edit_message_reply_markup(
                reply_markup=category_keyboard(chat_data["categories"])
            )
        elif data.startswith("cat:"):
            key = data[len("cat:"):]
            draft["category"] = next(
                (c["label"] for c in chat_data["categories"] if c["key"] == key),
                draft["category"],
            )
            await query.edit_message_text(
                format_card(draft),
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )
        elif data.startswith("edit:"):
            field = data[len("edit:"):]
            chat_data["awaiting_field"] = field
            await query.edit_message_text(
                f"{format_card(draft)}\n\n{FIELD_PROMPTS[field]}",
                reply_markup=back_only_keyboard(),
            )
        elif data == "back":
            await query.edit_message_text(
                format_card(draft),
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )

    async def _handle_invoice_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        data = query.data
        chat_data = context.chat_data

        if not chat_data.get("invoice_draft"):
            await query.answer("Questa fattura non è più in sospeso.", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=None)
            return

        await query.answer()
        chat_data["invoice_awaiting_field"] = None
        draft = chat_data["invoice_draft"]

        if data == "inv_confirm":
            await self._commit_invoice(update, context)
        elif data == "inv_cancel":
            self._clear_invoice(context)
            await query.edit_message_text("Fattura annullata.")
        elif data == "inv_back":
            await query.edit_message_text(
                format_invoice_card(draft), reply_markup=invoice_main_keyboard()
            )
        elif data.startswith("inv_edit:"):
            field = data[len("inv_edit:"):]
            chat_data["invoice_awaiting_field"] = field
            await query.edit_message_text(
                f"{format_invoice_card(draft)}\n\n{INV_FIELD_PROMPTS[field]}",
                reply_markup=invoice_back_keyboard(),
            )

    async def _finalize_card(self, query, text, reply_markup=None):
        """Chiude la card corrente e invia il risultato come nuovo messaggio.

        Serve a far scattare la notifica push: un edit non la genera. Il commit
        può richiedere tempo, quindi se l'utente ha lasciato la chat questo lo
        avvisa che l'operazione è conclusa. Ritorna il nuovo messaggio così il
        chiamante può aggiornare l'id della card in caso di errore ritentabile.
        """
        try:
            await query.message.delete()
        except Exception as delete_error:
            logger.debug("Could not delete card message: %s", delete_error)
        return await query.message.chat.send_message(text, reply_markup=reply_markup)

    async def _commit_invoice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        draft = context.chat_data["invoice_draft"]
        await query.edit_message_text("⏳ Sto salvando la fattura…")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/invoices/commit",
                    json=draft,
                    timeout=30.0,
                )
            response.raise_for_status()
            result = response.json()
        except Exception as error:
            logger.error("Invoice commit failed: %s", error)
            card = await self._finalize_card(
                query,
                f"{format_invoice_card(draft)}\n\n❌ Errore nel salvare. Riprova con Conferma.",
                reply_markup=invoice_main_keyboard(),
            )
            context.chat_data["invoice_card_message_id"] = card.message_id
            return

        if not result.get("success"):
            error = result.get("error", "Errore sconosciuto")
            logger.error("Invoice commit error: %s", error)
            card = await self._finalize_card(
                query,
                f"{format_invoice_card(draft)}\n\n❌ {error}\nRiprova con Conferma.",
                reply_markup=invoice_main_keyboard(),
            )
            context.chat_data["invoice_card_message_id"] = card.message_id
            return

        self._clear_invoice(context)
        await self._finalize_card(query, f"✅ {result['response']}")

    # ── Expense commit (unchanged) ────────────────────────────────────────────

    async def _commit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        draft = context.chat_data["draft"]
        await query.edit_message_text("⏳ Sto salvando la spesa…")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/agents/expenses/commit",
                    json=draft,
                    timeout=120.0,
                )
            response.raise_for_status()
            result = response.json()
        except Exception as error:
            logger.error("Commit request failed: %s", error)
            card = await self._finalize_card(
                query,
                f"{format_card(draft)}\n\n❌ Errore nel salvare. Riprova con Conferma.",
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )
            context.chat_data["card_message_id"] = card.message_id
            return

        if not result.get("success"):
            error = result.get("error", "Errore sconosciuto")
            logger.error("Commit error: %s", error)
            card = await self._finalize_card(
                query,
                f"{format_card(draft)}\n\n❌ Errore nel salvare: {error}\n"
                "Riprova con Conferma.",
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )
            context.chat_data["card_message_id"] = card.message_id
            return

        self._clear(context)
        await self._finalize_card(query, f"✅ {result['response']}")

    def run(self):
        """Avvia il bot in polling.

        Usa `Application.run_polling()` (sincrono, gestisce lui il loop e lo
        shutdown) invece di orchestrare a mano initialize/start/updater: è
        l'unico modo per cui gli hook `post_init`/`post_shutdown` registrati
        in `__init__` vengono eseguiti (vedi doc di `run_polling`), e sono
        questi hook ad avviare/fermare il server di ingest notifiche.
        """
        logger.info("Starting Telegram bot...")
        try:
            self.application.run_polling()
        finally:
            logger.info("Bot stopped.")
