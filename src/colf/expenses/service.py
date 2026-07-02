import logging

import gspread
from llama_cpp import Llama

from .llm.categorizer import categorize
from .llm.date_extractor import extract_date
from .llm.participants_extractor import extract_participants
from .constants import ITALIAN_MONTHS
from .domain import Expense
from .sharing import (
    compute_shares,
    extract_share_clause,
    filter_names,
    format_amount,
    parse_amount,
    split_names_fallback,
    strip_share_clause,
)
from .sheets import add_expense
from .text_parsing import extract_amount, extract_description

logger = logging.getLogger(__name__)


def parse_expense(message: str, *, llm: Llama) -> Expense:
    clause = extract_share_clause(message)
    participants: list[str] = []
    base = message
    if clause is not None:
        candidates = extract_participants(message, llm)
        participants = filter_names(candidates, message) or split_names_fallback(
            clause.tail
        )
        if participants:
            base = strip_share_clause(message)

    expense_date = extract_date(base, llm)
    raw_amount = extract_amount(base)

    amount = raw_amount or ""
    total_amount: str | None = None
    if participants and raw_amount:
        quota, user_share = compute_shares(parse_amount(raw_amount), len(participants))
        amount = format_amount(user_share)
        total_amount = raw_amount

    expense = Expense(
        day=expense_date.day,
        month=ITALIAN_MONTHS[expense_date.month - 1],
        description=extract_description(base),
        category=categorize(base, llm),
        amount=amount,
        total_amount=total_amount,
        participants=tuple(participants),
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
