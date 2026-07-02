from colf.expenses.llm.participants_extractor import extract_participants


class StubLlm:
    """Stub minimale di llama_cpp.Llama: risposta fissa."""

    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []

    def create_chat_completion(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"choices": [{"message": {"content": self.content}}]}


class TestExtractParticipants:
    def test_output_virgole(self):
        llm = StubLlm("Giulio, Bea")
        assert extract_participants("Pizza 30 da dividere con Giulio e Bea", llm) == [
            "Giulio",
            "Bea",
        ]

    def test_output_con_newline(self):
        llm = StubLlm("Anna\nLuca")
        assert extract_participants("x", llm) == ["Anna", "Luca"]

    def test_output_vuoto(self):
        llm = StubLlm("")
        assert extract_participants("x", llm) == []

    def test_spazi_ripuliti(self):
        llm = StubLlm("  Giulio ,  Bea  ")
        assert extract_participants("x", llm) == ["Giulio", "Bea"]

    def test_parametri_llm(self):
        llm = StubLlm("Marco")
        extract_participants("Cena 60 diviso con Marco", llm)
        call = llm.calls[0]
        assert call["temperature"] == 0.0
        assert "name extraction assistant" in call["messages"][0]["content"]
        assert "Cena 60 diviso con Marco" in call["messages"][1]["content"]
