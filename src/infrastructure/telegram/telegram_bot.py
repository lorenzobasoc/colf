import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        self.api_base_url = os.getenv('API_BASE_URL')
        self.application = Application.builder().token(self.bot_token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages and forward them to the expense agent."""
        user_message = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        logger.info(f"Received message from {username} ({user_id}): {user_message}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/api/agents/expenses/message",
                    json={"message": user_message},
                    timeout=120.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", False):
                        agent_response = result.get("response", "Nessuna risposta ricevuta.")
                        await update.message.reply_text(agent_response)
                    else:
                        error_msg = result.get("error", "Errore sconosciuto")
                        await update.message.reply_text(f"❌ Errore nel processare il messaggio: {error_msg}")
                        logger.error(f"API error: {error_msg}")
                else:
                    await update.message.reply_text("❌ Errore nel contattare il servizio spese. Riprova più tardi.")
                    logger.error(f"HTTP error: {response.status_code}")
                    
        except Exception as e:
            await update.message.reply_text("❌ Errore interno. Riprova più tardi.")
            logger.error(f"Unexpected error: {str(e)}")

    async def start_polling(self):
        """Start the bot with polling."""
        logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Bot is running. Press Ctrl+C to stop.")
        
        try:
            # Keep the bot running
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