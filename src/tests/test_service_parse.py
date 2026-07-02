from colf.expenses.service import parse_expense


class FakeLlm:
    """Fake di llama_cpp.Llama che risponde in base al tipo di prompt."""

    def __init__(self, participants: str = "Giulio, Bea"):
        self.participants = participants

    def create_chat_completion(self, messages, **kwargs):
        system = messages[0]["content"]
        if "name extraction assistant" in system:
            content = self.participants
        elif "date extraction assistant" in system:
            content = "02/07"
        else:  # categorizer
            content = "Cibo fuori"
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
