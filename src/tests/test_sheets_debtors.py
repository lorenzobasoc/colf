from decimal import Decimal

import pytest

from colf.expenses import service
from colf.expenses.domain import Expense
from colf.expenses.sheets import add_debtors


class FakeWorksheet:
    def __init__(self, block: list[list[str]]):
        self.block = block
        self.updates: list[tuple[str, list]] = []

    def get(self, range_name):
        return self.block

    def update(self, range_name, values, value_input_option=None):
        self.updates.append((range_name, values))


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


def _padded(rows: list[list[str]]) -> list[list[str]]:
    """Helper di test: righe attese seguite da padding vuoto fino a 20 righe."""
    return rows + [["", "", ""]] * (20 - len(rows))


class TestAddDebtors:
    def test_scrive_blocco_da_g25(self):
        ws = FakeWorksheet([])
        add_debtors(
            "Luglio",
            "Pizza",
            {"Giulio": Decimal("10"), "Bea": Decimal("10")},
            FakeClient(ws),
        )
        assert ws.updates == [
            (
                "G25:I44",
                _padded([["Giulio", "Pizza", "10"], ["Bea", "Pizza", "10"]]),
            )
        ]

    def test_persona_esistente_riceve_riga_sotto_senza_somma(self):
        ws = FakeWorksheet([["Giulio", "Pizza", "10"]])
        add_debtors("Luglio", "Cinema", {"Giulio": Decimal("5")}, FakeClient(ws))
        assert ws.updates == [
            (
                "G25:I44",
                _padded([["Giulio", "Pizza", "10"], ["", "Cinema", "5"]]),
            )
        ]

    def test_blocco_pieno_solleva(self):
        ws = FakeWorksheet([[f"Nome{i}", "Cena", "1"] for i in range(20)])
        with pytest.raises(ValueError, match="pieno"):
            add_debtors("Luglio", "Cena", {"Nuovo": Decimal("5")}, FakeClient(ws))
        assert ws.updates == []

    def test_righe_vuote_in_mezzo_vengono_sovrascritte_con_padding(self):
        """Riproduce il bug: l'utente ha cancellato a mano le righe dei
        debiti saldati (celle vuote in mezzo al blocco). Il blocco
        aggiornato è compattato da append_debts, ma la scrittura deve
        coprire l'intero range G25:I44 così che le vecchie righe fisiche
        sotto il nuovo blocco non restino come duplicati fantasma."""
        ws = FakeWorksheet(
            [
                ["", "", ""],
                ["", "", ""],
                ["Giulio", "Pizza", "10"],
                ["", "Cinema", "5"],
            ]
        )
        add_debtors("Luglio", "Aperitivo", {"Giulio": Decimal("8")}, FakeClient(ws))
        assert ws.updates == [
            (
                "G25:I44",
                _padded(
                    [
                        ["Giulio", "Pizza", "10"],
                        ["", "Cinema", "5"],
                        ["", "Aperitivo", "8"],
                    ]
                ),
            )
        ]

    def test_blocco_vuoto_scrive_padding_completo(self):
        """Caso 'ho cancellato tutto': existing == [] più una nuova spesa
        deve comunque scrivere l'intero blocco G25:I44 con padding."""
        ws = FakeWorksheet([])
        add_debtors(
            "Luglio",
            "Pizza",
            {"Giulio": Decimal("10")},
            FakeClient(ws),
        )
        assert ws.updates == [
            ("G25:I44", _padded([["Giulio", "Pizza", "10"]]))
        ]


SHARED = Expense(
    day=2,
    month="Luglio",
    description="Pizza",
    category="🍔 Cibo fuori",
    amount="10",
    total_amount="30",
    participants=("Giulio", "Bea"),
)

NORMAL = Expense(
    day=2, month="Luglio", description="Caffè", category="🍺 Bar", amount="1,20"
)


class TestCommitExpense:
    def test_normale_non_tocca_debitori(self, monkeypatch):
        monkeypatch.setattr(service, "add_expense", lambda e, c: None)
        called = []
        monkeypatch.setattr(
            service, "add_debtors", lambda m, desc, d, c: called.append(d)
        )
        summary = service.commit_expense(NORMAL, sheets_client=object())
        assert called == []
        assert "Debitori" not in summary

    def test_condivisa_aggiorna_debitori(self, monkeypatch):
        monkeypatch.setattr(service, "add_expense", lambda e, c: None)
        called = []
        monkeypatch.setattr(
            service,
            "add_debtors",
            lambda m, desc, d, c: called.append((m, desc, d)),
        )
        summary = service.commit_expense(SHARED, sheets_client=object())
        assert called == [
            ("Luglio", "Pizza", {"Giulio": Decimal("10"), "Bea": Decimal("10")})
        ]
        assert "Debitori aggiornati: Giulio 10, Bea 10" in summary

    def test_errore_debitori_riporta_avviso(self, monkeypatch):
        monkeypatch.setattr(service, "add_expense", lambda e, c: None)

        def boom(month, description, debts, client):
            raise ValueError("Blocco debitori pieno (max 20 righe).")

        monkeypatch.setattr(service, "add_debtors", boom)
        summary = service.commit_expense(SHARED, sheets_client=object())
        assert "Spesa registrata" in summary
        assert "⚠️" in summary
        assert "debitori NON aggiornati" in summary
