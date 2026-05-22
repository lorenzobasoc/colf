import os
import asyncio
import logging

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from expense_card import (
    FIELD_PROMPTS,
    back_only_keyboard,
    category_keyboard,
    format_card,
    main_keyboard,
    parse_date_input,
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

    @staticmethod
    def _clear(context: ContextTypes.DEFAULT_TYPE) -> None:
        for key in ("draft", "categories", "card_message_id", "awaiting_field"):
            context.chat_data.pop(key, None)

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        text = update.message.text
        chat_data = context.chat_data

        # 1. In attesa del valore di un campo da correggere.
        if chat_data.get("awaiting_field"):
            await self._apply_field_value(update, context, text)
            return

        # 2. Bozza in sospeso: blocca i nuovi messaggi di spesa.
        if chat_data.get("draft"):
            await update.message.reply_text(
                "⏳ Conferma o annulla prima la spesa in sospeso."
            )
            return

        # 3. Nuova spesa: parsing.
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
            format_card(result["draft"]), reply_markup=main_keyboard()
        )

    async def _apply_field_value(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
    ) -> None:
        field = context.chat_data["awaiting_field"]
        draft = context.chat_data["draft"]

        if field == "amount":
            draft["amount"] = text.strip()
        elif field == "description":
            draft["description"] = text.strip()
        elif field == "date":
            parsed = parse_date_input(text)
            if parsed is None:
                await update.message.reply_text(
                    "⚠️ Formato non valido. Usa gg/mm (es. 05/03)."
                )
                return  # awaiting_field resta impostato
            draft["day"], draft["month"] = parsed

        context.chat_data["awaiting_field"] = None
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=context.chat_data["card_message_id"],
            text=format_card(draft),
            reply_markup=main_keyboard(),
        )

    async def handle_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        data = query.data
        chat_data = context.chat_data

        # Bottone di una scheda vecchia, già risolta.
        if not chat_data.get("draft"):
            await query.answer("Questa spesa non è più in sospeso.", show_alert=True)
            await query.edit_message_reply_markup(reply_markup=None)
            return

        await query.answer()
        # Qualunque callback annulla una correzione campo in sospeso.
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
                format_card(draft), reply_markup=main_keyboard()
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
                format_card(draft), reply_markup=main_keyboard()
            )

    async def _commit(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        draft = context.chat_data["draft"]
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
                reply_markup=main_keyboard(),
            )
            return

        if not result.get("success"):
            error = result.get("error", "Errore sconosciuto")
            logger.error("Commit error: %s", error)
            await query.edit_message_text(
                f"{format_card(draft)}\n\n❌ Errore nel salvare: {error}\n"
                "Riprova con Conferma.",
                reply_markup=main_keyboard(),
            )
            return

        self._clear(context)
        await query.edit_message_text(f"✅ {result['response']}")

    async def start_polling(self):
        """Start the bot with polling."""
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
        """Run the bot using asyncio."""
        asyncio.run(self.start_polling())
