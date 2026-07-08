import asyncio
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
        self.application = Application.builder().token(self.bot_token).build()
        self._setup_handlers()

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
        for key in ("draft", "categories", "card_message_id", "awaiting_field"):
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
            await thinking.edit_text("❌ Errore nel processare il messaggio. Riprova.")
            return

        if not result.get("success"):
            logger.error("Parse error: %s", result.get("error"))
            await thinking.edit_text("❌ Errore nel processare il messaggio. Riprova.")
            return

        context.chat_data["draft"] = result["draft"]
        context.chat_data["categories"] = result["categories"]
        context.chat_data["card_message_id"] = thinking.message_id
        await thinking.edit_text(
            format_card(result["draft"]),
            reply_markup=main_keyboard(bool(result["draft"].get("participants"))),
        )

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
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=context.chat_data["card_message_id"],
            text=format_card(draft),
            reply_markup=main_keyboard(bool(draft.get("participants"))),
        )

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
            await thinking.edit_text("❌ Errore nella ricerca del cliente. Riprova.")
            return

        if not result.get("success"):
            await thinking.edit_text(
                f"❌ {result.get('error', 'Cliente non trovato.')}"
            )
            return

        context.chat_data["invoice_draft"] = result["draft"]
        context.chat_data["invoice_card_message_id"] = thinking.message_id
        await thinking.edit_text(
            format_invoice_card(result["draft"]), reply_markup=invoice_main_keyboard()
        )

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
            await query.edit_message_text(
                f"{format_invoice_card(draft)}\n\n❌ Errore nel salvare. Riprova con Conferma.",
                reply_markup=invoice_main_keyboard(),
            )
            return

        if not result.get("success"):
            error = result.get("error", "Errore sconosciuto")
            logger.error("Invoice commit error: %s", error)
            await query.edit_message_text(
                f"{format_invoice_card(draft)}\n\n❌ {error}\nRiprova con Conferma.",
                reply_markup=invoice_main_keyboard(),
            )
            return

        self._clear_invoice(context)
        await query.edit_message_text(f"✅ {result['response']}")

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
            await query.edit_message_text(
                f"{format_card(draft)}\n\n❌ Errore nel salvare. Riprova con Conferma.",
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )
            return

        if not result.get("success"):
            error = result.get("error", "Errore sconosciuto")
            logger.error("Commit error: %s", error)
            await query.edit_message_text(
                f"{format_card(draft)}\n\n❌ Errore nel salvare: {error}\n"
                "Riprova con Conferma.",
                reply_markup=main_keyboard(bool(draft.get("participants"))),
            )
            return

        self._clear(context)
        await query.edit_message_text(f"✅ {result['response']}")

    async def start_polling(self):
        logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Bot is running. Press Ctrl+C to stop.")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    def run(self):
        asyncio.run(self.start_polling())
