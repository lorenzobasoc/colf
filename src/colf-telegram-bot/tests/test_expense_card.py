from expense_card import (
    FIELD_PROMPTS,
    format_card,
    main_keyboard,
    parse_participants_input,
    recalc_share,
    share_quotas,
)


def make_draft(**overrides):
    draft = {
        "day": 2,
        "month": "Luglio",
        "description": "Pizza",
        "category": "🍔 Cibo fuori",
        "amount": "10",
        "total_amount": "30",
        "participants": ["Giulio", "Bea"],
    }
    draft.update(overrides)
    return draft


class TestShareQuotas:
    def test_divisione_esatta(self):
        assert share_quotas("30", 2) == ("10", "10")

    def test_resto_assorbito_dallutente(self):
        assert share_quotas("20", 2) == ("6,67", "6,66")

    def test_totale_non_parsabile(self):
        assert share_quotas("", 2) is None
        assert share_quotas("boh", 2) is None

    def test_zero_debitori(self):
        assert share_quotas("30", 0) is None


class TestRecalcShare:
    def test_aggiorna_amount(self):
        draft = make_draft(total_amount="20", amount="")
        recalc_share(draft)
        assert draft["amount"] == "6,66"

    def test_totale_invalido_non_tocca(self):
        draft = make_draft(total_amount="", amount="10")
        recalc_share(draft)
        assert draft["amount"] == "10"


class TestParseParticipantsInput:
    def test_nomi_virgola(self):
        assert parse_participants_input("giulio, bea") == ["Giulio", "Bea"]

    def test_nessuno(self):
        assert parse_participants_input("nessuno") == []
        assert parse_participants_input("  ") == []

    def test_dedupe(self):
        assert parse_participants_input("Bea, bea, Giulio") == ["Bea", "Giulio"]


class TestFormatCard:
    def test_scheda_normale_senza_chiavi_nuove(self):
        draft = {
            "day": 2,
            "month": "Luglio",
            "description": "Caffè",
            "category": "🍺 Bar",
            "amount": "1,20",
        }
        card = format_card(draft)
        assert "Importo: 1,20" in card
        assert "Condivisa" not in card

    def test_scheda_condivisa(self):
        card = format_card(make_draft())
        assert "Importo totale: 30" in card
        assert "👥 Condivisa con: Giulio, Bea" in card
        assert "Quota tua (nel foglio): 10" in card
        assert "Debitori: Giulio 10, Bea 10" in card

    def test_scheda_condivisa_senza_importo(self):
        card = format_card(make_draft(total_amount=None, amount=""))
        assert "(non rilevato)" in card
        assert "👥 Condivisa con: Giulio, Bea" in card


class TestMainKeyboard:
    def _callbacks(self, markup):
        return [b.callback_data for row in markup.inline_keyboard for b in row]

    def test_normale_senza_partecipanti(self):
        assert "edit:participants" not in self._callbacks(main_keyboard())

    def test_condivisa_con_partecipanti(self):
        callbacks = self._callbacks(main_keyboard(shared=True))
        assert "edit:participants" in callbacks

    def test_prompt_partecipanti_esiste(self):
        assert "participants" in FIELD_PROMPTS
