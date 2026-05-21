import logging
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

from ..config import Settings
from .constants import SHEET_HEADERS, SPREADSHEET_NAME_TEMPLATE
from .domain import Expense

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def create_sheets_client(settings: Settings) -> gspread.Client:
    credentials = Credentials.from_service_account_file(
        str(settings.service_account_path), scopes=_SCOPES
    )
    return gspread.authorize(credentials)


def add_expense(expense: Expense, client: gspread.Client) -> None:
    spreadsheet_name = SPREADSHEET_NAME_TEMPLATE.format(year=date.today().year)

    try:
        spreadsheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound as error:
        raise LookupError(f"Spreadsheet '{spreadsheet_name}' non trovato.") from error

    try:
        worksheet = spreadsheet.worksheet(expense.month)
    except gspread.WorksheetNotFound as error:
        raise LookupError(
            f"Foglio '{expense.month}' non trovato in '{spreadsheet_name}'."
        ) from error

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
    
    logger.info("Expense appended to '%s' / '%s' at row %d", spreadsheet_name, expense.month, next_row)