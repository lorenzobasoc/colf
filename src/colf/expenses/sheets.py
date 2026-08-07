import logging
from datetime import date
from decimal import Decimal

import gspread
from google.oauth2.service_account import Credentials

from ..config import Settings
from .constants import ITALIAN_MONTHS, SHEET_HEADERS, SPREADSHEET_NAME_TEMPLATE
from .domain import Expense
from .sharing import DebtorSummary, append_debts, parse_debtors_block

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DEBTORS_FIRST_ROW = 25
DEBTORS_MAX_ROWS = 20


def create_sheets_client(settings: Settings) -> gspread.Client:
    credentials = Credentials.from_service_account_file(
        str(settings.service_account_path), scopes=_SCOPES
    )
    return gspread.authorize(credentials)


def _open_month_worksheet(month: str, client: gspread.Client) -> gspread.Worksheet:
    spreadsheet_name = SPREADSHEET_NAME_TEMPLATE.format(year=date.today().year)
    try:
        spreadsheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound as error:
        raise LookupError(f"Spreadsheet '{spreadsheet_name}' non trovato.") from error
    try:
        return spreadsheet.worksheet(month)
    except gspread.WorksheetNotFound as error:
        raise LookupError(
            f"Foglio '{month}' non trovato in '{spreadsheet_name}'."
        ) from error


def add_expense(expense: Expense, client: gspread.Client) -> None:
    worksheet = _open_month_worksheet(expense.month, client)

    if not worksheet.acell("A1").value:
        worksheet.update("A1:D1", [SHEET_HEADERS])
        next_row = 2
    else:
        filled_rows = len(worksheet.col_values(1))
        next_row = filled_rows + 1

    target_range = f"A{next_row}:D{next_row}"

    row_data = [[expense.day, expense.description, expense.category, expense.amount]]

    worksheet.update(
        range_name=target_range,
        values=row_data,
        value_input_option="USER_ENTERED",
    )

    logger.info(
        "Expense appended to '%s' at row %d", expense.month, next_row
    )


def add_debtors(
    month: str, description: str, debts: dict[str, Decimal], client: gspread.Client
) -> None:
    worksheet = _open_month_worksheet(month, client)
    last_row = DEBTORS_FIRST_ROW + DEBTORS_MAX_ROWS - 1
    existing = worksheet.get(f"G{DEBTORS_FIRST_ROW}:I{last_row}")
    updated = append_debts(existing, description, debts)
    if len(updated) > DEBTORS_MAX_ROWS:
        raise ValueError(f"Blocco debitori pieno (max {DEBTORS_MAX_ROWS} righe).")

    worksheet.update(
        range_name=f"G{DEBTORS_FIRST_ROW}:I{DEBTORS_FIRST_ROW + len(updated) - 1}",
        values=updated,
        value_input_option="USER_ENTERED",
    )
    logger.info("Debtors block updated on '%s': %s", month, updated)


def read_debtors(month: str, client: gspread.Client) -> list[DebtorSummary]:
    """Legge (senza scrivere) il blocco debitori del mese e lo ritorna
    raggruppato per persona."""
    worksheet = _open_month_worksheet(month, client)
    last_row = DEBTORS_FIRST_ROW + DEBTORS_MAX_ROWS - 1
    existing = worksheet.get(f"G{DEBTORS_FIRST_ROW}:I{last_row}")
    return parse_debtors_block(existing)


def read_categorized_descriptions(client: gspread.Client) -> list[tuple[str, str]]:
    """Legge le spese gia' categorizzate dell'anno corrente come coppie
    (descrizione, categoria) in ordine cronologico (mesi in ordine, righe
    dall'alto), per il seed di CategoryCache. Non solleva: in caso di foglio
    mancante o errore su un mese ritorna cio' che ha raccolto."""
    spreadsheet_name = SPREADSHEET_NAME_TEMPLATE.format(year=date.today().year)
    try:
        spreadsheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        logger.warning("Spreadsheet '%s' non trovato.", spreadsheet_name)
        return []

    worksheets_by_title = {ws.title: ws for ws in spreadsheet.worksheets()}

    pairs: list[tuple[str, str]] = []
    for month in ITALIAN_MONTHS:
        worksheet = worksheets_by_title.get(month)
        if worksheet is None:
            continue
        try:
            rows = worksheet.get("B2:C")
        except Exception:
            logger.exception("Failed to read worksheet '%s' for category cache", month)
            continue
        for row in rows:
            if len(row) < 2:
                continue
            description = row[0].strip()
            category = row[1].strip()
            if not description or not category:
                continue
            if description.casefold() == "descrizione":
                continue
            pairs.append((description, category))

    return pairs
