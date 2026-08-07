from datetime import date
from decimal import Decimal

from colf.expenses import service
from colf.expenses.constants import ITALIAN_MONTHS
from colf.expenses.sharing import DebtorSummary, parse_debtors_block
from colf.expenses.sheets import read_debtors


class FakeWorksheet:
    def __init__(self, block: list[list[str]]):
        self.block = block
        self.get_calls: list[str] = []

    def get(self, range_name):
        self.get_calls.append(range_name)
        return self.block


class FakeSpreadsheet:
    def __init__(self, worksheet):
        self._worksheet = worksheet

    def worksheet(self, name):
        return self._worksheet


class FakeClient:
    def __init__(self, worksheet):
        self._spreadsheet = FakeSpreadsheet(worksheet)

    def open(self, name):
        return self._spreadsheet


class TestParseDebtorsBlock:
    def test_blocco_vuoto(self):
        assert parse_debtors_block([]) == []

    def test_gruppo_singolo_una_voce(self):
        result = parse_debtors_block([["Giulio", "Pizza", "10"]])
        assert result == [
            DebtorSummary(
                name="Giulio", items=(("Pizza", "10"),), total=Decimal("10")
            )
        ]

    def test_blocco_raggruppato_due_persone(self):
        block = [
            ["Giulio", "Pizza", "10"],
            ["", "Cinema", "5"],
            ["Bea", "Pizza", "10"],
        ]
        result = parse_debtors_block(block)
        assert result == [
            DebtorSummary(
                name="Giulio",
                items=(("Pizza", "10"), ("Cinema", "5")),
                total=Decimal("15"),
            ),
            DebtorSummary(name="Bea", items=(("Pizza", "10"),), total=Decimal("10")),
        ]

    def test_righe_vuote_o_senza_nome_iniziali_ignorate(self):
        block = [
            ["", "", ""],
            ["", "Fantasma", "1"],
            ["Giulio", "Pizza", "10"],
        ]
        result = parse_debtors_block(block)
        assert result == [
            DebtorSummary(
                name="Giulio", items=(("Pizza", "10"),), total=Decimal("10")
            )
        ]


class TestReadDebtors:
    def test_legge_blocco_dal_range_corretto(self):
        ws = FakeWorksheet(
            [
                ["Giulio", "Pizza", "10"],
                ["", "Cinema", "5"],
            ]
        )
        result = read_debtors("Luglio", FakeClient(ws))
        assert result == [
            DebtorSummary(
                name="Giulio",
                items=(("Pizza", "10"), ("Cinema", "5")),
                total=Decimal("15"),
            )
        ]
        assert ws.get_calls == ["G25:I44"]

    def test_blocco_vuoto_ritorna_lista_vuota(self):
        ws = FakeWorksheet([])
        assert read_debtors("Luglio", FakeClient(ws)) == []


class TestListDebtors:
    def test_ritorna_mese_corrente_e_debitori(self, monkeypatch):
        monkeypatch.setattr(
            service,
            "read_debtors",
            lambda month, client: [
                DebtorSummary(name="Giulio", items=(("Pizza", "10"),), total=Decimal("10"))
            ],
        )
        month, debtors = service.list_debtors(object())
        assert month == ITALIAN_MONTHS[date.today().month - 1]
        assert debtors == [
            DebtorSummary(name="Giulio", items=(("Pizza", "10"),), total=Decimal("10"))
        ]
