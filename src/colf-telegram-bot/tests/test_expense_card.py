from expense_card import (
    FIELD_PROMPTS,
    advance_batch,
    apply_field_value,
    format_card,
    main_keyboard,
    parse_participants_input,
    recalc_share,
    share_quotas,
    start_batch,
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

    def test_indicatore_progresso_con_batch(self):
        draft = {
            "day": 2,
            "month": "Luglio",
            "description": "Caffè",
            "category": "🍺 Bar",
            "amount": "1,20",
        }
        card = format_card(draft, 2, 3)
        assert "📝 Controlla la spesa (2/3)" in card

    def test_nessun_indicatore_con_totale_uno(self):
        draft = {
            "day": 2,
            "month": "Luglio",
            "description": "Caffè",
            "category": "🍺 Bar",
            "amount": "1,20",
        }
        card = format_card(draft, 1, 1)
        assert "📝 Controlla la spesa\n\n" in card
        assert "(1/1)" not in card

    def test_nessun_indicatore_senza_parametri(self):
        draft = {
            "day": 2,
            "month": "Luglio",
            "description": "Caffè",
            "category": "🍺 Bar",
            "amount": "1,20",
        }
        assert format_card(draft) == format_card(draft, None, None)
        assert "(" not in format_card(draft).split("\n\n")[0]

    def test_corpo_scheda_invariato_con_indicatore(self):
        draft = make_draft()
        senza = format_card(draft)
        con = format_card(draft, 2, 3)
        # Solo l'intestazione cambia, il resto del corpo è identico.
        assert senza.split("\n\n", 1)[1] == con.split("\n\n", 1)[1]


class TestStartBatch:
    def test_lista_vuota(self):
        assert start_batch([]) is None

    def test_primo_draft_e_stato(self):
        drafts = [make_draft(description="Pizza"), make_draft(description="Caffè")]
        draft, state = start_batch(drafts)
        assert draft["description"] == "Pizza"
        assert state == {
            "queue": [drafts[1]],
            "batch_index": 1,
            "batch_total": 2,
        }

    def test_singolo_draft(self):
        drafts = [make_draft()]
        draft, state = start_batch(drafts)
        assert draft == drafts[0]
        assert state == {"queue": [], "batch_index": 1, "batch_total": 1}


class TestAdvanceBatch:
    def test_coda_vuota_ritorna_none(self):
        assert advance_batch({"queue": [], "batch_index": 1, "batch_total": 1}) is None

    def test_stato_assente_ritorna_none(self):
        assert advance_batch({}) is None

    def test_estrae_prossimo_e_aggiorna_indice(self):
        second = make_draft(description="Caffè")
        state = {"queue": [second], "batch_index": 1, "batch_total": 2}
        draft = advance_batch(state)
        assert draft == second
        assert state["batch_index"] == 2
        assert state["queue"] == []


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


class TestApplyFieldValue:
    def test_importo_su_spesa_condivisa_aggiorna_totale_e_ricalcola(self):
        draft = make_draft(total_amount="30", amount="10")
        error = apply_field_value(draft, "amount", "60")
        assert error is None
        assert draft["total_amount"] == "60"
        assert draft["amount"] == "20"

    def test_importo_su_spesa_normale_imposta_amount(self):
        draft = {
            "day": 2,
            "month": "Luglio",
            "description": "Caffè",
            "category": "🍺 Bar",
            "amount": "1,20",
        }
        error = apply_field_value(draft, "amount", "2,50")
        assert error is None
        assert draft["amount"] == "2,50"

    def test_partecipanti_validi_aggiorna_e_ricalcola(self):
        draft = {
            "day": 2,
            "month": "Luglio",
            "description": "Pizza",
            "category": "🍔 Cibo fuori",
            "amount": "30",
        }
        error = apply_field_value(draft, "participants", "Giulio, Bea")
        assert error is None
        assert draft["participants"] == ["Giulio", "Bea"]
        assert draft["total_amount"] == "30"
        assert draft["amount"] == "10"

    def test_partecipanti_nessuno_torna_spesa_normale(self):
        draft = make_draft(total_amount="30", amount="10")
        error = apply_field_value(draft, "participants", "nessuno")
        assert error is None
        assert draft["amount"] == "30"
        assert draft["participants"] == []
        assert draft["total_amount"] is None

    def test_data_invalida_ritorna_errore_e_non_modifica(self):
        draft = make_draft()
        original = dict(draft)
        error = apply_field_value(draft, "date", "40/13")
        assert error == "⚠️ Formato non valido. Usa gg/mm (es. 05/03)."
        assert draft == original

    def test_descrizione_e_data_validi_funzionano(self):
        draft = make_draft()
        error = apply_field_value(draft, "description", "  Ristorante  ")
        assert error is None
        assert draft["description"] == "Ristorante"

        error = apply_field_value(draft, "date", "05/03")
        assert error is None
        assert draft["day"] == 5
        assert draft["month"] == "Marzo"
