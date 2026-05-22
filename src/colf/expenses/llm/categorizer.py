import logging

from llama_cpp import Llama

from ...config import Settings
from ..constants import CATEGORIES, FALLBACK_CATEGORY

logger = logging.getLogger(__name__)

_HEADER = """You are a local text classification assistant. Your sole task is to analyze the user's expense and respond EXCLUSIVELY with the name of one category from the list below.

CRITICAL RULES:
1. Respond with ONLY the category name (one or two words maximum).
2. DO NOT include emojis.
3. DO NOT add punctuation, introductions, explanations, or extra spaces.
4. Always output the exact Italian category name as written in the list below."""

_GUIDE = """CLASSIFICATION GUIDE:
- Supermarket, groceries, Aldi, Unes, ingredients -> Cibo
- Restaurant, pizza, McDonald, KFC, sushi, kebab, sandwich, dinner -> Cibo fuori
- Coffee, cafe, spritz, beer, breakfast, aperitivo, cornetto -> Bar
- Train, metro, bus, ticket, toll, pedaggio -> Trasporti
- Gas, gasoline, benzina, benza, car insurance -> Auto
- Netflix, Spotify, Amazon Prime, Disney+, subscription, abbonamento -> Abbonamenti
- Cinema, concert, theatre -> Intrattenimento
- If uncertain -> Altro"""


def _build_system_prompt() -> str:
    allowed = "\n".join(f"- {name}" for name in CATEGORIES)
    return f"{_HEADER}\n\nALLOWED CATEGORIES:\n{allowed}\n\n{_GUIDE}"


SYSTEM_PROMPT = _build_system_prompt()


def load_llm(settings: Settings) -> Llama:
    logger.info("Loading LLM from %s", settings.llm_model_path)
    return Llama(
        model_path=str(settings.llm_model_path),
        n_ctx=1024,
        chat_format="chatml",
        verbose=False,
    )


def categorize(message: str, llm: Llama) -> str:
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        temperature=0.0,
        max_tokens=16,
    )
    raw = response["choices"][0]["message"]["content"].strip()
    return _to_display_category(raw)


def _to_display_category(raw: str) -> str:
    normalized = raw.casefold()
    for name, display in CATEGORIES.items():
        if name.casefold() == normalized:
            return display
    return CATEGORIES[FALLBACK_CATEGORY]
