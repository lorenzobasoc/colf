import re

_AMOUNT_PATTERN = re.compile(r"\d+(\.\d+)?")
_AMOUNT_WITH_CURRENCY_PATTERN = re.compile(r"\d+([.,]\d+)?\s*(€|\$|£|euro|Euro)?")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def extract_amount(text: str) -> str | None:
    match = _AMOUNT_PATTERN.search(text.replace(",", "."))
    return match.group().replace(".", ",") if match else None


def extract_description(text: str) -> str:
    without_amount = _AMOUNT_WITH_CURRENCY_PATTERN.sub("", text)
    return _WHITESPACE_PATTERN.sub(" ", without_amount).strip()
