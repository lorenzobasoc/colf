import os
import asyncio
import logging
from typing import Optional
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, ContextTypes
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
        if not self.api_base_url:
             raise ValueError("API_BASE_URL environment variable is required")

        self.agent_id = "expenses" # Hardcoded as requested
        self.application = Application.builder().token(self.bot_token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def _ensure_customer_exists(self, client: httpx.AsyncClient, user_id: int, username: str):
        """Ensure the customer exists in Parlant, create if not found."""
        customer_id = str(user_id)
        try:
            # Check if customer exists
            response = await client.get(f"{self.api_base_url}/customers/{customer_id}")
            if response.status_code == 200:
                logger.debug(f"Customer {customer_id} already exists.")
                return
            
            # If not found (404), create it
            if response.status_code == 404:
                logger.info(f"Customer {customer_id} not found, creating...")
                create_response = await client.post(
                    f"{self.api_base_url}/customers",
                    json={
                        "id": customer_id,
                        "name": username
                })
                create_response.raise_for_status()
                logger.info(f"Customer {customer_id} created successfully.")
            else:
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to ensure customer {customer_id} exists: {e}")

    async def _get_or_create_session(self, client: httpx.AsyncClient, user_id: int, username: str) -> Optional[str]:
        """Find an existing session for the customer or create a new one."""
        customer_id = str(user_id)
        
        # Ensure customer exists first
        await self._ensure_customer_exists(client, user_id, username)
        
        # 1. Try to list existing sessions for this customer
        try:
            response = await client.get(
                f"{self.api_base_url}/sessions",
                params={"customer_id": customer_id, "agent_id": self.agent_id}
            )
            response.raise_for_status()
            sessions = response.json()
            
            # If we have active sessions, reuse the most recent one
            if sessions:
                return sessions[0]["id"]
                
        except Exception as e:
            logger.warning(f"Failed to list sessions for {customer_id}: {e}")

        # 2. Create a new session if none found
        try:
            response = await client.post(
                f"{self.api_base_url}/sessions",
                json={
                    "customer_id": customer_id,
                    "agent_id": self.agent_id,
                    "title": f"Telegram chat with {username}"
                }
            )
            response.raise_for_status()
            return response.json()["id"]
        except Exception as e:
            logger.error(f"Failed to create session for {customer_id}: {e}")
            return None

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming text messages and interop with Parlant."""
        user_message = update.message.text
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        logger.info(f"Received message from {username} ({user_id}): {user_message}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 1. Get Session ID
            session_id = await self._get_or_create_session(client, user_id, username)
            if not session_id:
                await update.message.reply_text("❌ Errore nella creazione della sessione.")
                return

            try:
                # 2. Post User Message
                post_response = await client.post(
                    f"{self.api_base_url}/sessions/{session_id}/events",
                    json={
                        "kind": "message",
                        "source": "customer",
                        "message": user_message
                    }
                )
                post_response.raise_for_status()
                user_event = post_response.json()
                
                # We start waiting for events AFTER this offset
                current_offset = user_event["offset"]
                min_offset = current_offset + 1

                # 3. Poll for Responses (Loop until session is idle)
                # Journey transitions can trigger multiple "ready" statuses as the agent moves between states.
                # We poll until we get no more events for a small period after a 'ready' status.
                last_status = None
                while True:
                    try:
                        poll_response = await client.get(
                            f"{self.api_base_url}/sessions/{session_id}/events",
                            params={
                                "min_offset": min_offset,
                                "wait_for_data": 60,
                            }
                        )
                        poll_response.raise_for_status()
                        events = poll_response.json()

                        if not isinstance(events, list) or not events:
                            # If we get no events (timeout), we check if the last status was 'ready'
                            # If so, we are likely done.
                            if last_status in ["ready", "error"]:
                                logger.info(f"Polling timeout and last status was {last_status}. finishing loop.")
                                break
                            # Otherwise, the agent might still be thinking, so we continue polling
                            logger.info("Polling timeout with no data, agent still processing...")
                            continue

                        for event in events:
                            min_offset = max(min_offset, event["offset"] + 1)
                            logger.info(f"Processing event: kind={event['kind']}, source={event['source']}, offset={event['offset']}")

                            if event["kind"] == "message" and event["source"] == "ai_agent":
                                agent_text = event["data"].get("message")
                                if agent_text:
                                    logger.info(f"Sending message to Telegram: {agent_text[:50]}...")
                                    await update.message.reply_text(agent_text)
                            
                            if event["kind"] == "status":
                                last_status = event["data"].get("status")
                                logger.info(f"Status update: {last_status}")
                                if last_status == "typing":
                                    await context.bot.send_chat_action(
                                        chat_id=update.effective_chat.id,
                                        action=ChatAction.TYPING
                                    )

                        # If the last item in this batch was 'ready', we do one quick check
                        # to see if a NEW turn started immediately (transition).
                        if last_status in ["ready", "error"]:
                            logger.info(f"Status is {last_status}, checking for immediate follow-up events...")
                            check_response = await client.get(
                                f"{self.api_base_url}/sessions/{session_id}/events",
                                params={
                                    "min_offset": min_offset,
                                    "wait_for_data": 2, # Small wait to catch immediate transitions
                                }
                            )
                            check_events = check_response.json()
                            if not isinstance(check_events, list) or not check_events:
                                logger.info("No more events found. Ending loop.")
                                break
                            else:
                                logger.info(f"Found {len(check_events)} more events after {last_status}. Continuing...")
                                # The loop will process these in the next iteration of 'while True'
                                # But wait, the next iteration will call .get again with wait_for_data=60. 
                                # Let's just fall through and let the loop handle them.
                                pass

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 504:
                            logger.debug("Polling timeout (504), retrying...")
                            continue
                        else:
                            raise

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error during conversation: {e.response.text}")
                await update.message.reply_text("❌ Errore di comunicazione con l'agente.")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await update.message.reply_text(f"❌ Errore imprevisto: {e}")

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