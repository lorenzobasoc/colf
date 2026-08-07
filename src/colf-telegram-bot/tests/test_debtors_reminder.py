from datetime import time

from debtors_reminder import format_debtors_reminder, parse_reminder_time


class TestFormatDebtorsReminder:
    def test_nessun_debitore_ritorna_none(self):
        assert format_debtors_reminder("Agosto", []) is None

    def test_un_debitore(self):
        debtors = [
            {
                "name": "Giulio",
                "total": "15",
                "items": [
                    {"description": "Pizza", "amount": "10"},
                    {"description": "Cinema", "amount": "5"},
                ],
            }
        ]
        text = format_debtors_reminder("Agosto", debtors)
        assert text is not None
        assert "Agosto" in text
        assert "Giulio" in text
        assert "15" in text
        assert "Pizza" in text
        assert "Cinema" in text

    def test_due_debitori(self):
        debtors = [
            {
                "name": "Giulio",
                "total": "15",
                "items": [{"description": "Pizza", "amount": "10"}],
            },
            {
                "name": "Bea",
                "total": "10",
                "items": [{"description": "Pizza", "amount": "10"}],
            },
        ]
        text = format_debtors_reminder("Agosto", debtors)
        assert text is not None
        assert "Giulio" in text
        assert "15" in text
        assert "Bea" in text
        assert "10" in text

    def test_debitore_senza_items(self):
        debtors = [{"name": "Giulio", "total": "15", "items": []}]
        text = format_debtors_reminder("Agosto", debtors)
        assert text is not None
        assert "Giulio" in text
        assert "15" in text


class TestParseReminderTime:
    def test_orario_valido(self):
        assert parse_reminder_time("08:30") == time(8, 30)

    def test_none_ritorna_default(self):
        assert parse_reminder_time(None) == time(9, 0)

    def test_stringa_vuota_ritorna_default(self):
        assert parse_reminder_time("") == time(9, 0)

    def test_invalido_non_numerico_ritorna_default(self):
        assert parse_reminder_time("nope") == time(9, 0)

    def test_invalido_fuori_range_ritorna_default(self):
        assert parse_reminder_time("25:99") == time(9, 0)

    def test_default_personalizzato(self):
        assert parse_reminder_time(None, default="10:15") == time(10, 15)

    def test_invalido_con_default_personalizzato(self):
        assert parse_reminder_time("boom", default="10:15") == time(10, 15)
