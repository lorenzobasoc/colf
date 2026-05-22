"""Helper puri per la scheda di conferma spesa: nessun I/O, nessuna chiamata Telegram."""
import re

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
}


def format_card(draft: dict) -> str:
    return (
        "📝 Controlla la spesa\n\n"
        f"Descrizione: {draft['description'] or '(vuota)'}\n"
        f"Importo: {draft['amount'] or '(non rilevato)'}\n"
        f"Categoria: {draft['category']}\n"
        f"Data: {draft['day']} {draft['month']}\n\n"
        "Tutto giusto?"
    )


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
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
    ])


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
