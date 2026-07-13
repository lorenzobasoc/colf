from colf.expenses.sharing import extract_share_clause, strip_share_clause, filter_names, split_names_fallback


class TestExtractShareClause:
    def test_da_dividere_con(self):
        clause = extract_share_clause("Pizza 30 da dividere con Giulio e Bea")
        assert clause is not None
        assert clause.tail == "Giulio e Bea"

    def test_diviso_con(self):
        clause = extract_share_clause("Cena 60 diviso con Marco")
        assert clause is not None
        assert clause.tail == "Marco"

    def test_divisa_con(self):
        clause = extract_share_clause("Spesa 40 divisa con Anna")
        assert clause is not None
        assert clause.tail == "Anna"

    def test_dividere_con_senza_da(self):
        clause = extract_share_clause("Benzina 50 dividere con Luca")
        assert clause is not None
        assert clause.tail == "Luca"

    def test_in_parti_uguali(self):
        clause = extract_share_clause(
            "Regalo 25 da dividere in parti uguali con Sara, Piero"
        )
        assert clause is not None
        assert clause.tail == "Sara, Piero"

    def test_case_insensitive(self):
        assert extract_share_clause("Pizza 30 DA DIVIDERE CON Bea") is not None

    def test_spesa_normale_none(self):
        assert extract_share_clause("Spesa esselunga 42,50") is None

    def test_con_senza_trigger_none(self):
        # "con" da solo NON è un trigger: "cena con Giulio" è una spesa normale
        assert extract_share_clause("Cena con Giulio 20") is None

    def test_condividere_non_matcha_a_meta_parola(self):
        # "condividere" contiene "divi..." ma non deve matchare a metà parola,
        # altrimenti "con" residuo di "condividere" resta appiccicato al testo estratto
        assert extract_share_clause("Cena 20 da condividere con Beatrice") is None


class TestStripShareClause:
    def test_rimuove_clausola(self):
        assert (
            strip_share_clause("Pizza 30 da dividere con Giulio e Bea") == "Pizza 30"
        )

    def test_messaggio_normale_invariato(self):
        assert strip_share_clause("Spesa esselunga 42,50") == "Spesa esselunga 42,50"

    def test_nessuno_spazio_residuo(self):
        result = strip_share_clause("Cena 60  diviso con Marco")
        assert result == "Cena 60"


class TestFilterNames:
    MSG = "Pizza 30 da dividere con Giulio e Bea"

    def test_nomi_presenti_accettati(self):
        assert filter_names(["Giulio", "Bea"], self.MSG) == ["Giulio", "Bea"]

    def test_nome_allucinato_scartato(self):
        assert filter_names(["Giulio", "Franco"], self.MSG) == ["Giulio"]

    def test_case_insensitive_e_normalizzazione(self):
        assert filter_names(["giulio", "BEA"], self.MSG) == ["Giulio", "Bea"]

    def test_dedupe_preserva_ordine(self):
        assert filter_names(["Bea", "Giulio", "bea"], self.MSG) == ["Bea", "Giulio"]

    def test_match_solo_parola_intera(self):
        # "Bea" non deve matchare dentro "Beatrice"
        assert filter_names(["Bea"], "Cena 20 da dividere con Beatrice") == []

    def test_candidati_vuoti_o_sporchi(self):
        assert filter_names(["", "  ", "Giulio,"], self.MSG) == ["Giulio"]


class TestSplitNamesFallback:
    def test_e_congiunzione(self):
        assert split_names_fallback("Giulio e Bea") == ["Giulio", "Bea"]

    def test_virgole_ed_e(self):
        assert split_names_fallback("Anna, Luca e Marco") == ["Anna", "Luca", "Marco"]

    def test_anche(self):
        assert split_names_fallback("Giulio e anche Marco") == ["Giulio", "Marco"]

    def test_nome_singolo(self):
        assert split_names_fallback("Marco") == ["Marco"]

    def test_bea_non_splittata_dalla_e_interna(self):
        assert split_names_fallback("Bea") == ["Bea"]

    def test_vuoto(self):
        assert split_names_fallback("") == []


from decimal import Decimal, InvalidOperation

import pytest

from colf.expenses.sharing import compute_shares, format_amount, parse_amount


class TestParseAmount:
    def test_virgola(self):
        assert parse_amount("42,50") == Decimal("42.50")

    def test_punto(self):
        assert parse_amount("6.67") == Decimal("6.67")

    def test_intero_con_euro(self):
        assert parse_amount("€ 30") == Decimal("30")

    def test_non_numerico_solleva(self):
        with pytest.raises(InvalidOperation):
            parse_amount("boh")


class TestFormatAmount:
    def test_intero_senza_decimali(self):
        assert format_amount(Decimal("10.00")) == "10"

    def test_decimali_con_virgola(self):
        assert format_amount(Decimal("6.67")) == "6,67"

    def test_un_decimale_padding(self):
        assert format_amount(Decimal("6.6")) == "6,60"


class TestComputeShares:
    def test_divisione_esatta(self):
        # 30 in 3 (utente + 2 debitori) → 10 a testa
        quota, user = compute_shares(Decimal("30"), 2)
        assert quota == Decimal("10.00")
        assert user == Decimal("10.00")

    def test_resto_assorbito_dallutente(self):
        # 20 in 3 → debitori 6,67 — utente 6,66
        quota, user = compute_shares(Decimal("20"), 2)
        assert quota == Decimal("6.67")
        assert user == Decimal("6.66")

    def test_somma_quote_uguale_totale(self):
        for total, n in [("20", 2), ("100", 3), ("7,77", 4), ("0,05", 2)]:
            quota, user = compute_shares(parse_amount(total), n)
            assert quota * n + user == parse_amount(total)

    def test_un_debitore(self):
        quota, user = compute_shares(Decimal("15"), 1)
        assert quota == Decimal("7.50")
        assert user == Decimal("7.50")


from colf.expenses.sharing import append_debts


class TestAppendDebts:
    def test_blocco_vuoto_un_debitore(self):
        result = append_debts([], "Pizza", {"Giulio": Decimal("10")})
        assert result == [["Giulio", "Pizza", "10"]]

    def test_blocco_vuoto_due_debitori_stessa_descrizione(self):
        result = append_debts(
            [], "Pizza", {"Giulio": Decimal("10"), "Bea": Decimal("10")}
        )
        assert result == [["Giulio", "Pizza", "10"], ["Bea", "Pizza", "10"]]

    def test_persona_esistente_riceve_nuova_spesa_sotto(self):
        existing = [["Giulio", "Pizza", "10"]]
        result = append_debts(existing, "Cinema", {"Giulio": Decimal("5")})
        assert result == [["Giulio", "Pizza", "10"], ["", "Cinema", "5"]]

    def test_persona_nuova_su_blocco_con_gruppi_esistenti(self):
        existing = [["Giulio", "Pizza", "10"]]
        result = append_debts(existing, "Pizza", {"Marco": Decimal("7")})
        assert result == [["Giulio", "Pizza", "10"], ["Marco", "Pizza", "7"]]

    def test_match_case_insensitive(self):
        existing = [["giulio", "Pizza", "10"]]
        result = append_debts(existing, "Cinema", {"Giulio": Decimal("2.50")})
        assert result == [["giulio", "Pizza", "10"], ["", "Cinema", "2,50"]]

    def test_righe_vuote_e_ragged_compattate(self):
        existing = [["Giulio", "Pizza", "10"], [], ["", "Cinema", "5"], ["Bea", "Pizza"]]
        result = append_debts(existing, "Regalo Anna", {"Marco": Decimal("3")})
        assert result == [
            ["Giulio", "Pizza", "10"],
            ["", "Cinema", "5"],
            ["Bea", "Pizza", ""],
            ["Marco", "Regalo Anna", "3"],
        ]

    def test_riga_nome_vuoto_prima_di_qualsiasi_nome_ignorata(self):
        existing = [["", "Fantasma", "1"], ["Giulio", "Pizza", "10"]]
        result = append_debts(existing, "Cinema", {"Giulio": Decimal("5")})
        assert result == [
            ["Giulio", "Pizza", "10"],
            ["", "Cinema", "5"],
        ]

    def test_importo_formato_italiano_preservato(self):
        result = append_debts([], "Cena", {"Bea": Decimal("7.50")})
        assert result == [["Bea", "Cena", "7,50"]]

    def test_gruppo_multi_riga_esempio_completo(self):
        existing = [
            ["Giulio", "Pizza", "10"],
            ["", "Cinema", "7,50"],
        ]
        result = append_debts(existing, "Regalo Anna", {"Giulio": Decimal("20")})
        assert result == [
            ["Giulio", "Pizza", "10"],
            ["", "Cinema", "7,50"],
            ["", "Regalo Anna", "20"],
        ]
