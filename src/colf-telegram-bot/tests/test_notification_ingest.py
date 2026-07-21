from unittest.mock import AsyncMock

from aiohttp.test_utils import AioHTTPTestCase

from notification_ingest import (
    INGEST_TOKEN_HEADER,
    NotificationIngestServer,
    build_parse_notification_request,
    check_token,
    create_ingest_server_from_env,
    validate_notification_payload,
)


class FakeBot:
    """Doppio minimale di TelegramBot: solo ciò che NotificationIngestServer usa."""

    def __init__(self):
        self.handle_bank_notification = AsyncMock(return_value="ok")


class TestCheckToken:
    def test_token_corretto(self):
        assert check_token("segreto", "segreto") is True

    def test_token_errato(self):
        assert check_token("sbagliato", "segreto") is False

    def test_token_mancante(self):
        assert check_token(None, "segreto") is False
        assert check_token("", "segreto") is False

    def test_expected_vuoto(self):
        assert check_token("qualcosa", "") is False


class TestValidateNotificationPayload:
    def test_payload_valido_completo(self):
        body = {
            "package": "com.bank.app",
            "title": "Pagamento",
            "text": "Esselunga 42,50",
            "posted_at": "2026-07-14T12:33:00",
        }
        payload, error = validate_notification_payload(body)
        assert error is None
        assert payload == {
            "package": "com.bank.app",
            "title": "Pagamento",
            "text": "Esselunga 42,50",
            "posted_at": "2026-07-14T12:33:00",
        }

    def test_solo_title(self):
        payload, error = validate_notification_payload({"title": "Pagamento", "text": ""})
        assert error is None
        assert payload["title"] == "Pagamento"
        assert payload["text"] == ""

    def test_solo_text(self):
        payload, error = validate_notification_payload({"title": "", "text": "Esselunga 42,50"})
        assert error is None
        assert payload["text"] == "Esselunga 42,50"

    def test_title_e_text_vuoti(self):
        payload, error = validate_notification_payload({"title": "  ", "text": ""})
        assert payload is None
        assert error is not None

    def test_campi_opzionali_mancanti(self):
        payload, error = validate_notification_payload({"title": "Pagamento", "text": "x"})
        assert error is None
        assert payload["package"] is None
        assert payload["posted_at"] is None

    def test_body_non_dict(self):
        payload, error = validate_notification_payload(["non", "un", "oggetto"])
        assert payload is None
        assert error is not None

    def test_body_none(self):
        payload, error = validate_notification_payload(None)
        assert payload is None
        assert error is not None

    def test_strip_whitespace(self):
        payload, error = validate_notification_payload({"title": "  Pagamento  ", "text": " x "})
        assert error is None
        assert payload["title"] == "Pagamento"
        assert payload["text"] == "x"


class TestBuildParseNotificationRequest:
    def test_mappatura_completa(self):
        payload = {
            "package": "com.bank.app",
            "title": "Pagamento",
            "text": "Esselunga 42,50",
            "posted_at": "2026-07-14T12:33:00",
        }
        request = build_parse_notification_request(payload)
        assert request == {
            "title": "Pagamento",
            "text": "Esselunga 42,50",
            "source": "com.bank.app",
            "posted_at": "2026-07-14T12:33:00",
        }

    def test_package_mancante_diventa_source_none(self):
        payload = {"package": None, "title": "Pagamento", "text": "x", "posted_at": None}
        request = build_parse_notification_request(payload)
        assert request["source"] is None
        assert request["posted_at"] is None


class TestCreateIngestServerFromEnv:
    def test_senza_ingest_token_ritorna_none(self, monkeypatch, caplog):
        monkeypatch.delenv("INGEST_TOKEN", raising=False)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        bot = FakeBot()
        with caplog.at_level("WARNING"):
            server = create_ingest_server_from_env(bot)
        assert server is None
        assert any("INGEST_TOKEN" in record.message for record in caplog.records)

    def test_senza_chat_id_ritorna_none(self, monkeypatch, caplog):
        monkeypatch.setenv("INGEST_TOKEN", "segreto")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        bot = FakeBot()
        with caplog.at_level("WARNING"):
            server = create_ingest_server_from_env(bot)
        assert server is None
        assert any("TELEGRAM_CHAT_ID" in record.message for record in caplog.records)

    def test_con_entrambe_le_env_ritorna_server(self, monkeypatch):
        monkeypatch.setenv("INGEST_TOKEN", "segreto")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        monkeypatch.delenv("INGEST_PORT", raising=False)
        bot = FakeBot()
        server = create_ingest_server_from_env(bot)
        assert isinstance(server, NotificationIngestServer)
        assert server.token == "segreto"
        assert server.port == 8080

    def test_porta_custom(self, monkeypatch):
        monkeypatch.setenv("INGEST_TOKEN", "segreto")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        monkeypatch.setenv("INGEST_PORT", "9090")
        bot = FakeBot()
        server = create_ingest_server_from_env(bot)
        assert server.port == 9090


class NotificationIngestServerTestCase(AioHTTPTestCase):
    """Test end-to-end sul server aiohttp: nessuna rete reale (TestClient usa
    un server in-process su una porta effimera) e nessuna chiamata Telegram
    reale (FakeBot mocka handle_bank_notification)."""

    TOKEN = "il-token-segreto"

    async def get_application(self):
        self.bot = FakeBot()
        self.server = NotificationIngestServer(self.bot, self.TOKEN, port=0)
        return self.server.build_app()

    async def test_health_senza_token_e_unauthorized(self):
        resp = await self.client.request("GET", "/ingest/health")
        assert resp.status == 401
        body = await resp.json()
        assert body == {"status": "unauthorized"}

    async def test_health_con_token_errato_e_unauthorized(self):
        resp = await self.client.request(
            "GET", "/ingest/health", headers={INGEST_TOKEN_HEADER: "sbagliato"}
        )
        assert resp.status == 401

    async def test_health_con_token_corretto(self):
        resp = await self.client.request(
            "GET", "/ingest/health", headers={INGEST_TOKEN_HEADER: self.TOKEN}
        )
        assert resp.status == 200
        body = await resp.json()
        assert body == {"status": "ok"}

    async def test_notification_senza_token_e_unauthorized(self):
        resp = await self.client.request(
            "POST", "/ingest/notification", json={"title": "t", "text": "x"}
        )
        assert resp.status == 401
        self.bot.handle_bank_notification.assert_not_awaited()

    async def test_notification_json_malformato_e_invalid(self):
        resp = await self.client.request(
            "POST",
            "/ingest/notification",
            headers={INGEST_TOKEN_HEADER: self.TOKEN},
            data="non è json",
        )
        assert resp.status == 400
        body = await resp.json()
        assert body == {"status": "invalid"}

    async def test_notification_payload_vuoto_e_invalid(self):
        resp = await self.client.request(
            "POST",
            "/ingest/notification",
            headers={INGEST_TOKEN_HEADER: self.TOKEN},
            json={"title": "", "text": "  "},
        )
        assert resp.status == 400
        body = await resp.json()
        assert body == {"status": "invalid"}
        self.bot.handle_bank_notification.assert_not_awaited()

        self.bot.handle_bank_notification.assert_not_awaited()

    async def test_notification_ok(self):
        self.bot.handle_bank_notification.return_value = "ok"
        resp = await self.client.request(
            "POST",
            "/ingest/notification",
            headers={INGEST_TOKEN_HEADER: self.TOKEN},
            json={
                "package": "com.bank.app",
                "title": "Pagamento",
                "text": "Esselunga 42,50",
                "posted_at": "2026-07-14T12:33:00",
            },
        )
        assert resp.status == 200
        body = await resp.json()
        assert body == {"status": "ok"}
        self.bot.handle_bank_notification.assert_awaited_once_with(
            {
                "package": "com.bank.app",
                "title": "Pagamento",
                "text": "Esselunga 42,50",
                "posted_at": "2026-07-14T12:33:00",
            }
        )

    async def test_notification_busy(self):
        self.bot.handle_bank_notification.return_value = "busy"
        resp = await self.client.request(
            "POST",
            "/ingest/notification",
            headers={INGEST_TOKEN_HEADER: self.TOKEN},
            json={"title": "Pagamento", "text": "Esselunga 42,50"},
        )
        assert resp.status == 409
        body = await resp.json()
        assert body == {"status": "busy"}

    async def test_notification_error(self):
        self.bot.handle_bank_notification.return_value = "error"
        resp = await self.client.request(
            "POST",
            "/ingest/notification",
            headers={INGEST_TOKEN_HEADER: self.TOKEN},
            json={"title": "Pagamento", "text": "Esselunga 42,50"},
        )
        assert resp.status == 502
        body = await resp.json()
        assert body == {"status": "error"}

    async def test_notification_eccezione_inattesa_e_error(self):
        self.bot.handle_bank_notification.side_effect = RuntimeError("boom")
        resp = await self.client.request(
            "POST",
            "/ingest/notification",
            headers={INGEST_TOKEN_HEADER: self.TOKEN},
            json={"title": "Pagamento", "text": "Esselunga 42,50"},
        )
        assert resp.status == 502
        body = await resp.json()
        assert body == {"status": "error"}


class TestBotStartsWithoutIngestEnv:
    """Criterio di accettazione: il bot deve avviarsi anche senza
    INGEST_TOKEN/TELEGRAM_CHAT_ID (server non avviato, solo un warning)."""

    def test_post_init_non_avvia_il_server_se_env_mancanti(self, monkeypatch, caplog):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake-token")
        monkeypatch.delenv("INGEST_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        import asyncio

        from telegram_bot import TelegramBot

        bot = TelegramBot()
        with caplog.at_level("WARNING"):
            asyncio.run(bot._post_init(bot.application))

        assert bot.ingest_server is None
        assert any("INGEST_TOKEN" in record.message for record in caplog.records)
