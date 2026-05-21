import logging
from datetime import date

import gspread
from llama_cpp import Llama

from .categorizer import categorize
from .constants import ITALIAN_MONTHS
from .domain import Expense
from .sheets import add_expense
from .text_parsing import extract_amount, extract_description

logger = logging.getLogger(__name__)


def record_expense(message: str, *, llm: Llama, sheets_client: gspread.Client) -> str:
    today = date.today()
    expense = Expense(
        day=today.day,
        month=ITALIAN_MONTHS[today.month - 1],
        description=extract_description(message),
        category=categorize(message, llm),
        amount=extract_amount(message) or "",
    )
    add_expense(expense, sheets_client)
    logger.info("Recorded expense: %s", expense)
    return (
        f"Spesa registrata: {expense.description or 'senza descrizione'} "
        f"- {expense.category} - {expense.amount or 'importo non rilevato'} "
        f"({expense.day} {expense.month})"
    )
