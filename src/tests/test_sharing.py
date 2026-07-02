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
