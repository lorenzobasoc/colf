from colf.expenses.notifications import extract_merchant, extract_notification_amount
from colf.expenses.service import categorize_description, parse_notification


class TestExtractNotificationAmount:
    def test_importo_con_presso(self):
        text = "Pagamento di 42,50 EUR presso ESSELUNGA SPA con carta *1234"
        assert extract_notification_amount(text) == "42,50"

    def test_importo_con_simbolo_euro_dopo(self):
        assert extract_notification_amount("Hai speso 12,00€ da AMAZON") == "12,00"

    def test_importo_con_eur_prima(self):
        assert extract_notification_amount("EUR 30,00 - MCDONALDS") == "30,00"

    def test_importo_con_simbolo_euro_prima(self):
        assert extract_notification_amount("€ 9,99 addebitati") == "9,99"

    def test_importo_con_punto_decimale_normalizzato(self):
        assert (
            extract_notification_amount("You spent €12.34 at Esselunga") == "12,34"
        )

    def test_importo_con_separatore_migliaia_rimosso(self):
        assert extract_notification_amount("Importo: 1.234,56 EUR") == "1234,56"

    def test_ignora_numero_carta_con_asterisco(self):
        assert extract_notification_amount("Pagamento con carta *1234") is None

    def test_ignora_numero_carta_terminante(self):
        assert extract_notification_amount("carta terminante 5678") is None

    def test_ignora_data_con_slash(self):
        assert extract_notification_amount("Pagamento il 14/07/2026") is None

    def test_ignora_data_e_orario(self):
        assert extract_notification_amount("Movimento del 14/07 12:33") is None

    def test_ignora_orario_con_alle(self):
        assert extract_notification_amount("Addebitato alle 12:33") is None

    def test_nessun_importo_trovato(self):
        assert extract_notification_amount("Accredito stipendio") is None

    def test_preferisce_candidato_con_valuta_vicina(self):
        # Il primo numero decimale ("1.500,00") non ha una valuta vicina; il
        # secondo ("42,50") sì, quindi vince quest'ultimo.
        text = "Saldo disponibile 1.500,00 - Pagamento di 42,50 EUR presso ESSELUNGA"
        assert extract_notification_amount(text) == "42,50"

    def test_fallback_al_primo_candidato_senza_valuta(self):
        text = "Movimento di 15,00 registrato, saldo residuo 200,00"
        assert extract_notification_amount(text) == "15,00"


class TestExtractMerchant:
    def test_presso_con_carta(self):
        text = "Pagamento di 42,50 EUR presso ESSELUNGA SPA con carta *1234"
        assert extract_merchant(text) == "Esselunga Spa"

    def test_presso_con_data_prima(self):
        text = "Acquisto di 12,00 EUR il 14/07 presso AMAZON.IT"
        assert extract_merchant(text) == "Amazon.it"

    def test_coda_dopo_trattino(self):
        text = "Pagamento POS EUR 30,00 - MCDONALDS MILANO"
        assert extract_merchant(text) == "Mcdonalds Milano"

    def test_c_o(self):
        text = "Addebito di 9,99 EUR c/o NETFLIX.COM"
        assert extract_merchant(text) == "Netflix.com"

    def test_at_gia_normalizzato(self):
        assert extract_merchant("You spent €12.34 at Esselunga") == "Esselunga"

    def test_a_favore_di(self):
        text = "Bonifico di 50,00 EUR a favore di MARIO ROSSI"
        assert extract_merchant(text) == "Mario Rossi"

    def test_su(self):
        text = "Pagamento di 20,00 EUR su NETFLIX"
        assert extract_merchant(text) == "Netflix"

    def test_nessun_marcatore_none(self):
        assert extract_merchant("Pagamento carta") is None

    def test_accredito_stipendio_none(self):
        assert extract_merchant("Accredito stipendio") is None

    def test_candidato_solo_cifre_none(self):
        assert extract_merchant("Pagamento di 10,00 EUR presso 1234") is None

    def test_esercente_che_inizia_per_eur_non_troncato(self):
        # Regressione: "eur" nel tail-cut deve avere \b, altrimenti "EUROSPIN"
        # (o EURONICS, EUROSPAR) viene troncato a stringa vuota.
        text = "Pagamento di 23,50 EUR presso EUROSPIN"
        assert extract_merchant(text) == "Eurospin"

    def test_marcatore_debole_prima_non_blocca_marcatore_valido_dopo(self):
        # Regressione: "su" (in "Addebito su carta") precede "presso" nel testo;
        # deve fallire su quel candidato e riprovare con "presso ESSELUNGA".
        text = "Addebito su carta *1234: pagamento di 42,50 EUR presso ESSELUNGA"
        assert extract_merchant(text) == "Esselunga"

    def test_marcatore_forte_ha_priorita_su_debole_anche_se_valido(self):
        # Regressione: "su POS" (marcatore debole "su") produce un candidato
        # normalizzabile ("Pos"), ma "presso ESSELUNGA" (marcatore forte) più
        # avanti deve comunque vincere. Formato bancario reale ("Pagamento su
        # POS ...", tipico di Intesa e simili).
        text = "Pagamento su POS di 42,50 EUR presso ESSELUNGA"
        assert extract_merchant(text) == "Esselunga"

    def test_marcatore_debole_unico_continua_a_funzionare(self):
        text = "Pagamento su AMAZON.IT di 12,00 EUR"
        assert extract_merchant(text) == "Amazon.it"

    def test_importo_dopo_il_nome_esercente_tagliato(self):
        # Regressione: l'importo che segue il nome ("ESSELUNGA di 42,50 EUR")
        # non deve restare silenziosamente nella descrizione.
        text = "Pagamento presso ESSELUNGA di 42,50 EUR"
        assert extract_merchant(text) == "Esselunga"


class FakeLlm:
    """Fake di llama_cpp.Llama: ritorna sempre la stessa categoria."""

    def __init__(self, category: str = "Cibo"):
        self.category = category

    def create_chat_completion(self, messages, **kwargs):
        return {"choices": [{"message": {"content": self.category}}]}


class TestParseNotification:
    def test_merchant_estratto_chiama_llm(self):
        text = "Pagamento di 42,50 EUR presso ESSELUNGA SPA con carta *1234"
        expense, needs_description = parse_notification(
            "Pagamento carta", text, "2026-07-14T12:33:00", llm=FakeLlm()
        )
        assert needs_description is False
        assert expense.description == "Esselunga Spa"
        assert expense.category == "🍲 Cibo/Spesa"
        assert expense.amount == "42,50"
        assert expense.total_amount is None
        assert expense.participants == ()
        assert expense.day == 14
        assert expense.month == "Luglio"

    def test_merchant_non_estratto_niente_llm_ne_fallback(self):
        expense, needs_description = parse_notification(
            "Pagamento carta", "", None, llm=FakeLlm()
        )
        assert needs_description is True
        assert expense.description == ""
        assert expense.category == "🌟 Altro extra"

    def test_posted_at_assente_usa_oggi(self):
        from datetime import date

        expense, _ = parse_notification("Accredito stipendio", "", None, llm=FakeLlm())
        today = date.today()
        assert expense.day == today.day

    def test_posted_at_con_z_finale(self):
        expense, _ = parse_notification(
            "Pagamento carta", "", "2026-01-05T10:00:00Z", llm=FakeLlm()
        )
        assert expense.day == 5
        assert expense.month == "Gennaio"


class TestCategorizeDescription:
    def test_descrizione_vuota_niente_llm(self):
        assert categorize_description("", llm=FakeLlm()) == "🌟 Altro extra"

    def test_descrizione_whitespace_niente_llm(self):
        assert categorize_description("   ", llm=FakeLlm()) == "🌟 Altro extra"

    def test_descrizione_valida_chiama_llm(self):
        assert categorize_description("Esselunga", llm=FakeLlm()) == "🍲 Cibo/Spesa"
