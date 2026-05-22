import logging

import gspread
from llama_cpp import Llama

from .llm.categorizer import categorize
from .llm.date_extractor import extract_date
from .constants import ITALIAN_MONTHS
from .domain import Expense
from .sheets import add_expense
from .text_parsing import extract_amount, extract_description

logger = logging.getLogger(__name__)


def parse_expense(message: str, *, llm: Llama) -> Expense:
    expense_date = extract_date(message, llm)
    expense = Expense(
        day=expense_date.day,
        month=ITALIAN_MONTHS[expense_date.month - 1],
        description=extract_description(message),
        category=categorize(message, llm),
        amount=extract_amount(message) or "",
    )
    logger.info("Parsed expense draft: %s", expense)
    return expense


def commit_expense(expense: Expense, *, sheets_client: gspread.Client) -> str:
    add_expense(expense, sheets_client)
    logger.info("Recorded expense: %s", expense)
    return (
        f"Spesa registrata: {expense.description or 'senza descrizione'} "
        f"- {expense.category} - {expense.amount or 'importo non rilevato'} "
        f"({expense.day} {expense.month})"
    )
