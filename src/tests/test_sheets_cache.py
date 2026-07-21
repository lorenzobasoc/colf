import gspread

from colf.expenses.sheets import read_categorized_descriptions


class FakeWorksheet:
    def __init__(self, title, rows=None, raises=False):
        self.title = title
        self._rows = rows or []
        self._raises = raises

    def get(self, range_name):
        if self._raises:
            raise RuntimeError("boom")
        return self._rows


class FakeSpreadsheet:
    def __init__(self, worksheets):
        self._worksheets = worksheets

    def worksheets(self):
        return self._worksheets


class FakeClient:
    def __init__(self, spreadsheet=None, not_found=False):
        self._spreadsheet = spreadsheet
        self._not_found = not_found

    def open(self, name):
        if self._not_found:
            raise gspread.SpreadsheetNotFound()
        return self._spreadsheet


class TestReadCategorizedDescriptions:
    def test_raccoglie_mesi_in_ordine_cronologico(self):
        gennaio = FakeWorksheet("Gennaio", [["Driutti", "🍺 Bar"]])
        luglio = FakeWorksheet("Luglio", [["Esselunga", "🍲 Cibo/Spesa"]])
        # Passati fuori ordine: la funzione deve comunque restituirli in
        # ordine cronologico (Gennaio prima di Luglio).
        spreadsheet = FakeSpreadsheet([luglio, gennaio])
        client = FakeClient(spreadsheet)

        result = read_categorized_descriptions(client)

        assert result == [
            ("Driutti", "🍺 Bar"),
            ("Esselunga", "🍲 Cibo/Spesa"),
        ]

    def test_salta_righe_header_corte_o_vuote(self):
        ws = FakeWorksheet(
            "Luglio",
            [
                ["Descrizione", "Tipologia"],
                ["SoloUnaColonna"],
                ["", ""],
                ["  ", "🍺 Bar"],
                ["Driutti", "  "],
                ["Driutti", "🍺 Bar"],
            ],
        )
        spreadsheet = FakeSpreadsheet([ws])
        client = FakeClient(spreadsheet)

        result = read_categorized_descriptions(client)

        assert result == [("Driutti", "🍺 Bar")]

    def test_mese_che_solleva_viene_saltato(self):
        boom = FakeWorksheet("Gennaio", raises=True)
        ok = FakeWorksheet("Luglio", [["Driutti", "🍺 Bar"]])
        spreadsheet = FakeSpreadsheet([boom, ok])
        client = FakeClient(spreadsheet)

        result = read_categorized_descriptions(client)

        assert result == [("Driutti", "🍺 Bar")]

    def test_mese_senza_worksheet_viene_saltato(self):
        luglio = FakeWorksheet("Luglio", [["Driutti", "🍺 Bar"]])
        spreadsheet = FakeSpreadsheet([luglio])
        client = FakeClient(spreadsheet)

        result = read_categorized_descriptions(client)

        assert result == [("Driutti", "🍺 Bar")]

    def test_spreadsheet_non_trovato_ritorna_vuoto(self):
        client = FakeClient(not_found=True)
        assert read_categorized_descriptions(client) == []
