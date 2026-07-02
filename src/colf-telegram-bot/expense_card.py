"""Helper puri per la scheda di conferma spesa: nessun I/O, nessuna chiamata Telegram."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

ITALIAN_MONTHS: tuple[str, ...] = (
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
)

_DATE_INPUT = re.compile(r"^\s*(\d{1,2})/(\d{1,2})\s*$")

FIELD_PROMPTS: dict[str, str] = {
    "amount": "✏️ Scrivi il nuovo importo (es. 42,50):",
    "description": "✏️ Scrivi la nuova descrizione:",
    "date": "✏️ Scrivi la nuova data in formato gg/mm (es. 05/03):",
    "participants": (
        "✏️ Scrivi i partecipanti separati da virgola (es. Giulio, Bea).\n"
        "Scrivi 'nessuno' per tornare a spesa normale:"
    ),
}


_CENT = Decimal("0.01")


def _parse_amount(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace("€", "").replace(" ", "").replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def _format_amount(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return str(value.quantize(_CENT)).replace(".", ",")


def share_quotas(total_raw: str, n_debtors: int) -> tuple[str, str] | None:
    """(quota_debitore, quota_utente) come stringhe italiane; None se il
    totale non è parsabile o non ci sono debitori."""
    total = _parse_amount(total_raw or "")
    if total is None or n_debtors < 1:
        return None
    quota = (total / (n_debtors + 1)).quantize(_CENT, rounding=ROUND_HALF_UP)
    user_share = total - quota * n_debtors
    return _format_amount(quota), _format_amount(user_share)


def recalc_share(draft: dict) -> None:
    """Aggiorna draft["amount"] (quota utente) da total_amount e participants."""
    quotas = share_quotas(
        draft.get("total_amount") or "", len(draft.get("participants") or [])
    )
    if quotas is not None:
        draft["amount"] = quotas[1]


def parse_participants_input(text: str) -> list[str]:
    """Nomi separati da virgola; '' o 'nessuno' → lista vuota."""
    cleaned = text.strip()
    if not cleaned or cleaned.lower() == "nessuno":
        return []
    seen: set[str] = set()
    names: list[str] = []
    for part in cleaned.split(","):
        name = part.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name.capitalize())
    return names


def format_card(draft: dict) -> str:
    participants = draft.get("participants") or []
    if not participants:
        return (
            "📝 Controlla la spesa\n\n"
            f"Descrizione: {draft['description'] or '(vuota)'}\n"
            f"Importo: {draft['amount'] or '(non rilevato)'}\n"
            f"Categoria: {draft['category']}\n"
            f"Data: {draft['day']} {draft['month']}\n\n"
            "Tutto giusto?"
        )

    total = draft.get("total_amount") or ""
    quotas = share_quotas(total, len(participants))
    if quotas is None:
        quota_lines = "Quote: (importo non rilevato)"
    else:
        debtor_quota, user_quota = quotas
        debtors = ", ".join(f"{name} {debtor_quota}" for name in participants)
        quota_lines = (
            f"Quota tua (nel foglio): {user_quota}\n"
            f"Debitori: {debtors}"
        )
    return (
        "📝 Controlla la spesa\n\n"
        f"Descrizione: {draft['description'] or '(vuota)'}\n"
        f"Importo totale: {total or '(non rilevato)'}\n"
        f"👥 Condivisa con: {', '.join(participants)}\n"
        f"{quota_lines}\n"
        f"Categoria: {draft['category']}\n"
        f"Data: {draft['day']} {draft['month']}\n\n"
        "Tutto giusto?"
    )


def main_keyboard(shared: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("✅ Conferma", callback_data="confirm"),
            InlineKeyboardButton("❌ Annulla", callback_data="cancel"),
        ],
        [
            InlineKeyboardButton("✏️ Descrizione", callback_data="edit:description"),
            InlineKeyboardButton("✏️ Importo", callback_data="edit:amount"),
        ],
        [
            InlineKeyboardButton("✏️ Categoria", callback_data="edit:category"),
            InlineKeyboardButton("✏️ Data", callback_data="edit:date"),
        ],
    ]
    if shared:
        rows.append(
            [InlineKeyboardButton("✏️ Partecipanti", callback_data="edit:participants")]
        )
    return InlineKeyboardMarkup(rows)


def category_keyboard(categories: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(categories), 2):
        rows.append([
            InlineKeyboardButton(c["label"], callback_data=f"cat:{c['key']}")
            for c in categories[i:i + 2]
        ])
    rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back")])
    return InlineKeyboardMarkup(rows)


def back_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Indietro", callback_data="back")]
    ])


def _days_in_month(month: int) -> int:
    if month == 2:
        return 29
    return 30 if month in (4, 6, 9, 11) else 31


def parse_date_input(text: str) -> tuple[int, str] | None:
    """Parsa 'gg/mm' in (giorno, nome_mese_italiano). Ritorna None se invalido."""
    match = _DATE_INPUT.match(text)
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12):
        return None
    if not (1 <= day <= _days_in_month(month)):
        return None
    return day, ITALIAN_MONTHS[month - 1]
