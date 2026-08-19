from colf.expenses.text_parsing import split_messages


class TestSplitMessages:
    def test_singola_riga(self):
        assert split_messages("Pizza 30") == ["Pizza 30"]

    def test_piu_righe(self):
        assert split_messages("Pizza 30\nSpesa esselunga 42,50") == [
            "Pizza 30",
            "Spesa esselunga 42,50",
        ]

    def test_punto_e_virgola_come_separatore(self):
        assert split_messages("Pizza 30; Spesa esselunga 42,50") == [
            "Pizza 30",
            "Spesa esselunga 42,50",
        ]

    def test_righe_vuote_scartate(self):
        assert split_messages("Pizza 30\n\n\nSpesa esselunga 42,50\n") == [
            "Pizza 30",
            "Spesa esselunga 42,50",
        ]

    def test_input_vuoto(self):
        assert split_messages("") == []

    def test_solo_separatori(self):
        assert split_messages("\n;;\n") == []
