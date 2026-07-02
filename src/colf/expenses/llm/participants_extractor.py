import logging

from llama_cpp import Llama

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a name extraction assistant. The user sends an Italian expense message where the cost is split with other people.

Output ONLY the first names of the OTHER people (never the author), separated by commas. Nothing else.

Examples:
"Pizza 30 da dividere con Giulio e Bea" → Giulio, Bea
"Cena 60 diviso con Marco" → Marco
"Sushi 45,50 da dividere con Anna, Luca e Marco" → Anna, Luca, Marco
"Benzina 40 da dividere in parti uguali con i miei coinquilini Paolo e Franca" → Paolo, Franca
"Regalo 25 diviso con anche Sara" → Sara"""


def extract_participants(message: str, llm: Llama) -> list[str]:
    """Ritorna i nomi candidati estratti dall'LLM. Il chiamante applica il
    guardrail (sharing.filter_names) e l'eventuale fallback."""
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Expense: {message}"},
        ],
        temperature=0.0,
        max_tokens=32,
    )
    raw = response["choices"][0]["message"]["content"].strip()
    logger.info("Participants LLM raw output: %r", raw)
    return [p for p in (part.strip() for part in raw.replace("\n", ",").split(",")) if p]
