"""Pure helpers for the invoice confirmation card — no I/O, no Telegram API calls."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

INV_FIELD_PROMPTS: dict[str, str] = {
    "amount": "✏️ Scrivi il nuovo importo in euro (es. 1500.00):",
    "description": "✏️ Scrivi la nuova descrizione:",
    "date": "✏️ Scrivi la nuova data di emissione in formato YYYY-MM-DD (es. 2026-06-01):",
    "giorni": "✏️ Scrivi i giorni di pagamento (es. 30):",
}


def format_invoice_card(draft: dict) -> str:
    return (
        "🧾 Controlla la fattura\n\n"
        f"Cliente: {draft['ragione_sociale']}\n"
        f"Descrizione: {draft['descrizione'] or '(vuota)'}\n"
        f"Importo: € {draft['importo']}\n"
        f"Data emissione: {draft['data_emissione']}\n"
        f"Giorni pagamento: {draft['giorni_pagamento']}\n\n"
        "Tutto giusto?"
    )


def invoice_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Conferma", callback_data="inv_confirm"),
            InlineKeyboardButton("❌ Annulla", callback_data="inv_cancel"),
        ],
        [
            InlineKeyboardButton("✏️ Importo", callback_data="inv_edit:amount"),
            InlineKeyboardButton("✏️ Descrizione", callback_data="inv_edit:description"),
        ],
        [
            InlineKeyboardButton("✏️ Data", callback_data="inv_edit:date"),
            InlineKeyboardButton("✏️ Giorni pag.", callback_data="inv_edit:giorni"),
        ],
    ])


def invoice_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Indietro", callback_data="inv_back")]
    ])
