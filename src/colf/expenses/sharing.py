"""Logica pura per le spese condivise: nessun I/O, nessuna chiamata LLM."""
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# Clausola di condivisione: matcha fino a fine messaggio.
# Varianti: "da dividere con", "dividere con", "diviso/divisa con",
# "da dividere in parti uguali con".
_SHARE_CLAUSE = re.compile(
    r"\s*(?:da\s+)?divi(?:dere|so|sa)(?:\s+in\s+parti\s+uguali)?\s+con\s+(?P<tail>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ShareClause:
    tail: str


def extract_share_clause(message: str) -> ShareClause | None:
    m = _SHARE_CLAUSE.search(message)
    if m is None:
        return None
    return ShareClause(tail=m.group("tail"))


def strip_share_clause(message: str) -> str:
    m = _SHARE_CLAUSE.search(message)
    if m is None:
        return message
    return message[: m.start()].strip()


_NAME_SPLIT = re.compile(r"\s*(?:,|\banche\b|\be\b)\s*", re.IGNORECASE)
_NAME_JUNK = ".,;:!?"


def filter_names(candidates: list[str], message: str) -> list[str]:
    """Guardrail anti-allucinazione: tiene solo i nomi presenti come parola
    intera nel messaggio originale. Dedupe case-insensitive, ordine preservato."""
    seen: set[str] = set()
    valid: list[str] = []
    for raw in candidates:
        name = raw.strip().strip(_NAME_JUNK)
        if not name:
            continue
        if not re.search(rf"\b{re.escape(name)}\b", message, re.IGNORECASE):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        valid.append(name.capitalize())
    return valid


def split_names_fallback(tail: str) -> list[str]:
    """Fallback deterministico se l'LLM non produce nomi validi: split della
    coda clausola su virgole, "e", "anche"."""
    seen: set[str] = set()
    names: list[str] = []
    for part in _NAME_SPLIT.split(tail):
        name = part.strip().strip(_NAME_JUNK)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name.capitalize())
    return names


_CENT = Decimal("0.01")


def parse_amount(raw: str) -> Decimal:
    """Parsa un importo in formato italiano ("6,67") o con punto ("6.67").
    Solleva decimal.InvalidOperation se non numerico."""
    cleaned = raw.replace("€", "").replace(" ", "").replace(",", ".")
    return Decimal(cleaned)


def format_amount(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return str(value.quantize(_CENT)).replace(".", ",")


def compute_shares(total: Decimal, n_debtors: int) -> tuple[Decimal, Decimal]:
    """Ritorna (quota_debitore, quota_utente): quota debitore arrotondata a
    2 decimali, l'utente assorbe i centesimi di resto."""
    n = n_debtors + 1
    quota = (total / n).quantize(_CENT, rounding=ROUND_HALF_UP)
    user_share = total - quota * n_debtors
    return quota, user_share
