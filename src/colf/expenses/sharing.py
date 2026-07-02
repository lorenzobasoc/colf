"""Logica pura per le spese condivise: nessun I/O, nessuna chiamata LLM."""
import re
from dataclasses import dataclass

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
