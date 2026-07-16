import logging
from datetime import date, datetime

import gspread
from llama_cpp import Llama

from .llm.categorizer import categorize
from .llm.date_extractor import extract_date
from .llm.participants_extractor import extract_participants
from .constants import CATEGORIES, FALLBACK_CATEGORY, ITALIAN_MONTHS
from .domain import Expense
from .notifications import extract_merchant, extract_notification_amount
from .sharing import (
    compute_shares,
    extract_share_clause,
    filter_names,
    format_amount,
    parse_amount,
    split_names_fallback,
    strip_share_clause,
)
from .sheets import add_debtors, add_expense
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
    summary = (
        f"Spesa registrata: {expense.description or 'senza descrizione'} "
        f"- {expense.category} - {expense.amount or 'importo non rilevato'} "
        f"({expense.day} {expense.month})"
    )
    if not (expense.participants and expense.total_amount):
        return summary

    quota, _ = compute_shares(
        parse_amount(expense.total_amount), len(expense.participants)
    )
    debts = {name: quota for name in expense.participants}
    try:
        add_debtors(expense.month, expense.description, debts, sheets_client)
    except Exception as error:
        logger.exception("Failed to update debtors block")
        return (
            f"{summary}\n⚠️ Spesa registrata, ma debitori NON aggiornati: {error}"
        )
    debtors_text = ", ".join(
        f"{name} {format_amount(amount)}" for name, amount in debts.items()
    )
    return f"{summary}\nDebitori aggiornati: {debtors_text}"


def _parse_posted_at(posted_at: str | None) -> date:
    if posted_at is None:
        return date.today()
    try:
        return datetime.fromisoformat(posted_at.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def parse_notification(
    title: str, text: str, posted_at: str | None, *, llm: Llama
) -> tuple[Expense, bool]:
    combined = f"{title} {text}"
    amount = extract_notification_amount(combined) or ""
    merchant = extract_merchant(combined)
    needs_description = merchant is None
    category = (
        CATEGORIES[FALLBACK_CATEGORY]
        if needs_description
        else categorize(merchant, llm)
    )
    expense_date = _parse_posted_at(posted_at)
    expense = Expense(
        day=expense_date.day,
        month=ITALIAN_MONTHS[expense_date.month - 1],
        description=merchant or "",
        category=category,
        amount=amount,
        total_amount=None,
        participants=(),
    )
    logger.info("Parsed notification expense draft: %s", expense)
    return expense, needs_description


def categorize_description(description: str, *, llm: Llama) -> str:
    if not description.strip():
        return CATEGORIES[FALLBACK_CATEGORY]
    return categorize(description, llm)
