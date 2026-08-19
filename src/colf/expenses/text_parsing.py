import re

# Separatori per più spese in un unico messaggio Telegram.
_MESSAGE_SPLIT_PATTERN = re.compile(r"[\n;]+")

# Matches numbers with optional decimal (comma or dot) and optional currency symbol.
_AMOUNT_WITH_CURRENCY_PATTERN = re.compile(r"\d+([.,]\d+)?\s*(€|\$|£|euro|Euro)?")
# Collapses multiple spaces into one for final cleanup.
_WHITESPACE_PATTERN = re.compile(r"\s+")

# These three patterns strip numeric date references so they are not mistaken for amounts.
# Date *understanding* is handled by the LLM in date_extractor.py.

# Matches "il 3", "il 31/12", "il 01/01/2025".
_IL_DATE_STRIP = re.compile(
    r"\bil\s+\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)?\b", re.IGNORECASE
)
# Matches standalone "31/12" or "01/01/2025" (not already removed by _IL_DATE_STRIP).
_SLASH_DATE_STRIP = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
# Matches "5 marzo", "31 dicembre", etc.
_DAY_MONTH_STRIP = re.compile(
    r"\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio"
    r"|agosto|settembre|ottobre|novembre|dicembre)\b",
    re.IGNORECASE,
)


def _strip_date_refs(text: str) -> str:
    # _IL_DATE_STRIP runs first so "il 31/12" is removed as a whole;
    # _SLASH_DATE_STRIP then catches any bare "dd/mm" not preceded by "il".
    text = _IL_DATE_STRIP.sub("", text)
    text = _SLASH_DATE_STRIP.sub("", text)
    text = _DAY_MONTH_STRIP.sub("", text)
    return text


def strip_amount(text: str) -> str:
    """Return the message with the amount removed, preserving date references.
    Used by date_extractor to avoid the LLM confusing prices with day numbers."""
    without_dates = _strip_date_refs(text)
    matches = list(_AMOUNT_WITH_CURRENCY_PATTERN.finditer(without_dates))
    if not matches:
        return text
    amount = matches[-1].group().strip()
    idx = text.rfind(amount)
    if idx == -1:
        return text
    return _WHITESPACE_PATTERN.sub(" ", text[:idx] + text[idx + len(amount) :]).strip()


def split_messages(text: str) -> list[str]:
    """Divide un messaggio in più segmenti spesa, uno per riga/`;`.
    Split deterministico, nessun LLM. Segmenti vuoti/solo-whitespace scartati."""
    return [segment.strip() for segment in _MESSAGE_SPLIT_PATTERN.split(text) if segment.strip()]


def extract_amount(text: str) -> str | None:
    # Strip date numbers first to avoid "31/12" being picked as the amount.
    without_dates = _strip_date_refs(text)
    matches = list(_AMOUNT_WITH_CURRENCY_PATTERN.finditer(without_dates))
    if not matches:
        return None
    # Pattern is "Descrizione Importo Data": the amount is always the last number.
    raw = matches[-1].group().strip()
    return raw.replace(".", ",") if "." in raw else raw


def extract_description(text: str) -> str:
    without_dates = _strip_date_refs(text)
    matches = list(_AMOUNT_WITH_CURRENCY_PATTERN.finditer(without_dates))
    # Everything before the last number is the description.
    # This preserves product numbers in the name (e.g. "iPhone 15 cover 25" → "iPhone 15 cover").
    before_amount = without_dates[: matches[-1].start()] if matches else without_dates
    return _WHITESPACE_PATTERN.sub(" ", before_amount).strip()
