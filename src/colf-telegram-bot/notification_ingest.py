"""Server HTTP di ingest per le notifiche bancarie.

Un'app Android intercetta le notifiche di pagamento e le inoltra qui via
HTTP. Il modulo espone:

- funzioni pure di validazione (token, payload, mappatura verso la request
  dell'API `/parse-notification`), testabili senza rete;
- `NotificationIngestServer`, un piccolo server `aiohttp` che il bot avvia
  dentro il proprio processo (hook `post_init`/`post_shutdown`
  dell'`Application` di python-telegram-bot).

La logica di dominio (chiamare l'API di parsing, mandare la scheda spesa in
chat, gestire il caso "già occupato") vive in `TelegramBot.handle_bank_notification`
(in `telegram_bot.py`): questo modulo si limita a validare la richiesta HTTP
e a tradurre l'esito in una risposta JSON.
"""
import hmac
import logging
import os
from typing import Any, TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

INGEST_NOTIFICATION_PATH = "/ingest/notification"
INGEST_HEALTH_PATH = "/ingest/health"

INGEST_TOKEN_HEADER = "X-Ingest-Token"

# Mappa l'esito di TelegramBot.handle_bank_notification allo status HTTP da
# restituire all'app Android.
_RESULT_STATUS_CODES: dict[str, int] = {
    "ok": 200,
    "busy": 409,
    "error": 502,
}


def check_token(provided: str | None, expected: str) -> bool:
    """Confronta il token ricevuto con quello atteso a tempo costante."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def validate_notification_payload(body: Any) -> tuple[dict, None] | tuple[None, str]:
    """Valida il body JSON di `POST /ingest/notification`.

    Ritorna `(payload_normalizzato, None)` se valido, `(None, motivo)`
    altrimenti. `title` e `text` vengono normalizzati (stripped); `package` e
    `posted_at` sono opzionali e passano invariati.
    """
    if not isinstance(body, dict):
        return None, "il body non è un oggetto JSON"

    title = (body.get("title") or "").strip()
    text = (body.get("text") or "").strip()
    if not title and not text:
        return None, "title e text sono entrambi vuoti"

    return {
        "package": body.get("package"),
        "title": title,
        "text": text,
        "posted_at": body.get("posted_at"),
    }, None


def build_parse_notification_request(payload: dict) -> dict:
    """Mappa il payload di ingest (già validato) nella request JSON per
    `POST /api/agents/expenses/parse-notification`."""
    return {
        "title": payload.get("title") or "",
        "text": payload.get("text") or "",
        "source": payload.get("package"),
        "posted_at": payload.get("posted_at"),
    }


class NotificationIngestServer:
    """Server HTTP `aiohttp` che riceve le notifiche bancarie e le inoltra al
    bot Telegram. Espone `POST /ingest/notification` e `GET /ingest/health`,
    entrambi protetti dall'header `X-Ingest-Token`.
    """

    def __init__(self, bot: "TelegramBot", token: str, port: int = 8080) -> None:
        self.bot = bot
        self.token = token
        self.port = port
        self._runner: web.AppRunner | None = None

    def _authorized(self, request: web.Request) -> bool:
        return check_token(request.headers.get(INGEST_TOKEN_HEADER), self.token)

    async def handle_health(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return web.json_response({"status": "unauthorized"}, status=401)
        return web.json_response(
            {"status": "ok", "enabled": bool(self.bot.notifications_enabled)}
        )

    async def handle_notification(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return web.json_response({"status": "unauthorized"}, status=401)

        try:
            body = await request.json()
        except Exception as error:
            logger.info("Notifica ingest con JSON malformato: %s", error)
            return web.json_response({"status": "invalid"}, status=400)

        payload, error_reason = validate_notification_payload(body)
        if payload is None:
            logger.info("Notifica ingest scartata (%s)", error_reason)
            return web.json_response({"status": "invalid"}, status=400)

        if not self.bot.notifications_enabled:
            logger.info(
                "Notifica ingest ricevuta ma feature disattivata: %r", payload["title"]
            )
            return web.json_response({"status": "disabled"})

        try:
            result = await self.bot.handle_bank_notification(payload)
        except Exception as error:
            logger.error("Errore inatteso nella gestione della notifica: %s", error)
            return web.json_response({"status": "error"}, status=502)

        status_code = _RESULT_STATUS_CODES.get(result, 502)
        return web.json_response({"status": result}, status=status_code)

    def build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_post(INGEST_NOTIFICATION_PATH, self.handle_notification)
        app.router.add_get(INGEST_HEALTH_PATH, self.handle_health)
        return app

    async def start(self) -> None:
        app = self.build_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info("Server di ingest notifiche avviato su 0.0.0.0:%s", self.port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            logger.info("Server di ingest notifiche fermato.")


def create_ingest_server_from_env(bot: "TelegramBot") -> NotificationIngestServer | None:
    """Costruisce il server di ingest leggendo la configurazione dall'ambiente.

    Ritorna `None` (e logga un warning esplicito) se `INGEST_TOKEN` o
    `TELEGRAM_CHAT_ID` non sono impostati: in tal caso il server non va
    avviato e il bot continua a funzionare normalmente, senza la feature di
    ingest da notifiche.
    """
    token = os.getenv("INGEST_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning(
            "Server di ingest notifiche non avviato: impostare INGEST_TOKEN e "
            "TELEGRAM_CHAT_ID nell'ambiente per abilitarlo."
        )
        return None

    port = int(os.getenv("INGEST_PORT", "8080"))
    return NotificationIngestServer(bot, token, port)
