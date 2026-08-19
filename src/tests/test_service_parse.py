from colf.expenses.category_cache import CategoryCache
from colf.expenses.domain import Expense
from colf.expenses.service import commit_expense, parse_expense, parse_expenses


class FakeLlm:
    """Fake di llama_cpp.Llama che risponde in base al tipo di prompt."""

    def __init__(self, participants: str = "Giulio, Bea"):
        self.participants = participants
        self.categorizer_calls = 0

    def create_chat_completion(self, messages, **kwargs):
        system = messages[0]["content"]
        if "name extraction assistant" in system:
            content = self.participants
        elif "date extraction assistant" in system:
            content = "02/07"
        elif "text classification assistant" in system:  # categorizer
            self.categorizer_calls += 1
            content = "Cibo fuori"
        else:
            content = "02/07"
        return {"choices": [{"message": {"content": content}}]}


class TestParseExpenseCondivisa:
    def test_spesa_condivisa_completa(self):
        expense = parse_expense(
            "Pizza 30 da dividere con Giulio e Bea", llm=FakeLlm()
        )
        assert expense.participants == ("Giulio", "Bea")
        assert expense.total_amount == "30"
        assert expense.amount == "10"  # quota utente: 30 / 3
        assert expense.description == "Pizza"
        assert expense.category == "🍔 Cibo fuori"
        assert expense.day == 2
        assert expense.month == "Luglio"

    def test_resto_assorbito_dallutente(self):
        expense = parse_expense(
            "Pizza 20 da dividere con Giulio e Bea", llm=FakeLlm()
        )
        assert expense.amount == "6,66"
        assert expense.total_amount == "20"

    def test_guardrail_scarta_nome_allucinato(self):
        expense = parse_expense(
            "Pizza 30 da dividere con Giulio e Bea",
            llm=FakeLlm(participants="Giulio, Franco"),
        )
        assert expense.participants == ("Giulio",)
        assert expense.amount == "15"  # 30 / 2

    def test_fallback_se_llm_vuoto(self):
        expense = parse_expense(
            "Pizza 30 da dividere con Giulio e Bea", llm=FakeLlm(participants="")
        )
        assert expense.participants == ("Giulio", "Bea")

    def test_spesa_normale_invariata(self):
        expense = parse_expense("Spesa esselunga 42,50", llm=FakeLlm())
        assert expense.participants == ()
        assert expense.total_amount is None
        assert expense.amount == "42,50"

    def test_condivisa_senza_importo(self):
        expense = parse_expense("Pizza da dividere con Giulio e Bea", llm=FakeLlm())
        assert expense.participants == ("Giulio", "Bea")
        assert expense.amount == ""
        assert expense.total_amount is None


class TestParseExpenseCategoryCache:
    def test_cache_seeded_evita_chiamata_llm(self):
        cache = CategoryCache(loader=lambda: [])
        cache.remember("Driutti", "🍺 Bar")
        llm = FakeLlm()

        expense = parse_expense("Driutti 5", llm=llm, category_cache=cache)

        assert expense.description == "Driutti"
        assert expense.category == "🍺 Bar"
        assert llm.categorizer_calls == 0

    def test_cache_miss_ricade_su_llm(self):
        cache = CategoryCache(loader=lambda: [])
        llm = FakeLlm()

        expense = parse_expense("Driutti 5", llm=llm, category_cache=cache)

        assert expense.category == "🍔 Cibo fuori"
        assert llm.categorizer_calls == 1

    def test_senza_cache_comportamento_invariato(self):
        expense = parse_expense("Driutti 5", llm=FakeLlm())
        assert expense.category == "🍔 Cibo fuori"

    def test_commit_aggiorna_cache_per_parse_successivo(self, monkeypatch):
        from colf.expenses import service

        monkeypatch.setattr(service, "add_expense", lambda e, c: None)
        monkeypatch.setattr(service, "add_debtors", lambda m, desc, d, c: None)

        cache = CategoryCache(loader=lambda: [])
        confirmed = Expense(
            day=2,
            month="Luglio",
            description="Driutti",
            category="🍺 Bar",
            amount="5",
        )
        commit_expense(confirmed, sheets_client=object(), category_cache=cache)

        llm = FakeLlm()
        expense = parse_expense("Driutti 5", llm=llm, category_cache=cache)

        assert expense.category == "🍺 Bar"
        assert llm.categorizer_calls == 0


class TestParseExpenses:
    def test_messaggio_multiriga_ordine_corretto(self):
        expenses = parse_expenses(
            "Pizza 30\nSpesa esselunga 42,50", llm=FakeLlm()
        )
        assert len(expenses) == 2
        assert expenses[0].description == "Pizza"
        assert expenses[1].description == "Spesa esselunga"

    def test_messaggio_singolo_identico_a_parse_expense(self):
        [expense] = parse_expenses("Spesa esselunga 42,50", llm=FakeLlm())
        assert expense == parse_expense("Spesa esselunga 42,50", llm=FakeLlm())

    def test_condivisione_si_applica_solo_alla_sua_riga(self):
        expenses = parse_expenses(
            "Pizza 30 da dividere con Giulio e Bea\nSpesa esselunga 42,50",
            llm=FakeLlm(),
        )
        assert expenses[0].participants == ("Giulio", "Bea")
        assert expenses[0].amount == "10"
        assert expenses[1].participants == ()
        assert expenses[1].amount == "42,50"
