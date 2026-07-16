"""Parsing puro delle notifiche push bancarie: nessun I/O, nessuna chiamata LLM."""
import re

# Importo: richiede una parte decimale di 2 cifre per non confondersi con numeri di
# carta ("*1234"), date ("14/07") e orari ("12:33"), che non usano "," o "." come
# separatore. Il gruppo ripetuto da 3 cifre opzionale gestisce il separatore delle
# migliaia ("1.234,56"); i lookaround evitano di spezzare sequenze di cifre più lunghe.
_MONEY_PATTERN = re.compile(r"(?<!\d)\d{1,3}(?:[.,]\d{3})*[.,]\d{2}(?!\d)")

_CURRENCY_MARKER = re.compile(r"EUR|€|euro", re.IGNORECASE)

_WHITESPACE = re.compile(r"\s+")

# Marcatori espliciti di esercente, in due livelli di priorità. Nessun gruppo di
# cattura fino a fine stringa: ogni marcatore trovato (finditer) viene provato come
# candidato indipendente, così un marcatore incontrato per primo nel testo ma "più
# debole" non impedisce di arrivare a un marcatore migliore più avanti.
# Forti: inequivocabili, quasi mai falsi positivi ("presso", "c/o", "a favore di", "at").
_MERCHANT_MARKER_STRONG = re.compile(
    r"\b(?:presso|c/o|a favore di|at)\b", re.IGNORECASE
)
# Deboli: parole generiche che ricorrono spesso in frasi bancarie non legate
# all'esercente ("Pagamento su POS ...", "Addebito su carta ..."); provate solo
# se nessun marcatore forte produce un candidato valido.
_MERCHANT_MARKER_WEAK = re.compile(r"\b(?:su)\b", re.IGNORECASE)
# Fallback se nessun marcatore esplicito produce un candidato valido: coda dopo
# l'ultimo trattino finale (es. "EUR 30,00 - MCDONALDS MILANO").
_MERCHANT_DASH = re.compile(r"[-—]\s*(?P<merchant>[^-—]+)$")

# Marcatori di fine esercente: da qui in poi il testo non fa più parte del nome.
# "eur"/"euro" hanno \b su entrambi i lati per non troncare esercenti che
# iniziano con quelle lettere (es. "EUROSPIN", "EURONICS"); il simbolo "€" resta
# senza \b perché non è un carattere di parola. L'importo che segue il nome
# (es. "ESSELUNGA di 42,50 EUR") va tagliato insieme all'eventuale "di" che lo
# introduce, altrimenti resterebbe silenziosamente nella descrizione.
_MERCHANT_TAIL = re.compile(
    r"\b(?:con\s+carta|carta|il\s+\d{1,2}(?:/\d{1,2}(?:/\d{2,4})?)?"
    r"|alle\s+\d{1,2}[:.]\d{2}|importo|eur|euro)\b"
    r"|€"
    r"|(?:\bdi\s+)?" + _MONEY_PATTERN.pattern,
    re.IGNORECASE,
)

_TRAILING_PUNCT = ".,;:!?"


def extract_notification_amount(text: str) -> str | None:
    matches = list(_MONEY_PATTERN.finditer(text))
    if not matches:
        return None
    # Preferisci il primo candidato con un marcatore di valuta vicino (prima o
    # dopo, finestra di 20 caratteri); altrimenti ricadi sul primo candidato.
    for match in matches:
        start, end = match.start(), match.end()
        context = text[max(0, start - 20) : start] + text[end : end + 20]
        if _CURRENCY_MARKER.search(context):
            return _normalize_amount(match.group())
    return _normalize_amount(matches[0].group())


def _normalize_amount(raw: str) -> str:
    if "." in raw and "," in raw:
        return raw.replace(".", "")
    if "." in raw:
        return raw.replace(".", ",")
    return raw


def extract_merchant(text: str) -> str | None:
    for markers in (_MERCHANT_MARKER_STRONG, _MERCHANT_MARKER_WEAK):
        for marker in markers.finditer(text):
            candidate = _normalize_merchant(_cut_tail(text[marker.end() :]))
            if candidate is not None:
                return candidate
    dash = _MERCHANT_DASH.search(text)
    if dash is None:
        return None
    return _normalize_merchant(_cut_tail(dash.group("merchant")))


def _cut_tail(merchant: str) -> str:
    tail = _MERCHANT_TAIL.search(merchant)
    return merchant[: tail.start()] if tail else merchant


def _normalize_merchant(raw: str) -> str | None:
    cleaned = _WHITESPACE.sub(" ", raw).strip().strip(_TRAILING_PUNCT)
    if len(cleaned) < 2 or not re.search(r"[^\W\d_]", cleaned):
        return None
    if cleaned.isupper():
        cleaned = " ".join(word.capitalize() for word in cleaned.split(" "))
    return cleaned
