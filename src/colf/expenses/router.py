import logging
from dataclasses import asdict

import gspread
from fastapi import APIRouter, Depends
from llama_cpp import Llama

from .category_cache import CategoryCache
from .constants import CATEGORIES
from .dependencies import get_category_cache, get_llm, get_sheets_client
from .domain import Expense
from .schemas import (
    CategorizeRequest,
    CategorizeResponse,
    CategoryOption,
    CommitResponse,
    DebtorGroup,
    DebtorItem,
    DebtorsResponse,
    ExpenseDraft,
    MessageRequest,
    NotificationRequest,
    ParseNotificationResponse,
    ParseResponse,
)
from .service import (
    categorize_description,
    commit_expense,
    list_debtors,
    parse_expense,
    parse_notification,
)
from .sharing import format_amount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents/expenses", tags=["expenses"])


def _category_options() -> list[CategoryOption]:
    return [CategoryOption(key=key, label=label) for key, label in CATEGORIES.items()]


@router.post("/parse", response_model=ParseResponse)
def parse_message(
    payload: MessageRequest,
    llm: Llama = Depends(get_llm),
    cache: CategoryCache = Depends(get_category_cache),
) -> ParseResponse:
    try:
        expense = parse_expense(payload.message, llm=llm, category_cache=cache)
        draft = ExpenseDraft(**asdict(expense))
        return ParseResponse(draft=draft, categories=_category_options(), success=True)
    except Exception as error:
        logger.exception("Failed to parse expense")
        return ParseResponse(success=False, error=str(error))


@router.post("/commit", response_model=CommitResponse)
def commit_message(
    draft: ExpenseDraft,
    sheets_client: gspread.Client = Depends(get_sheets_client),
    cache: CategoryCache = Depends(get_category_cache),
) -> CommitResponse:
    try:
        expense = Expense(
            day=draft.day,
            month=draft.month,
            description=draft.description,
            category=draft.category,
            amount=draft.amount,
            total_amount=draft.total_amount,
            participants=tuple(draft.participants),
        )
        summary = commit_expense(expense, sheets_client=sheets_client, category_cache=cache)
        return CommitResponse(response=summary, success=True)
    except Exception as error:
        logger.exception("Failed to commit expense")
        return CommitResponse(response="", success=False, error=str(error))


@router.post("/parse-notification", response_model=ParseNotificationResponse)
def parse_notification_message(
    payload: NotificationRequest,
    llm: Llama = Depends(get_llm),
    cache: CategoryCache = Depends(get_category_cache),
) -> ParseNotificationResponse:
    try:
        expense, needs_description = parse_notification(
            payload.title,
            payload.text,
            payload.posted_at,
            llm=llm,
            category_cache=cache,
        )
        draft = ExpenseDraft(**asdict(expense))
        return ParseNotificationResponse(
            draft=draft,
            categories=_category_options(),
            needs_description=needs_description,
            success=True,
        )
    except Exception as error:
        logger.exception("Failed to parse notification")
        return ParseNotificationResponse(success=False, error=str(error))


@router.post("/categorize", response_model=CategorizeResponse)
def categorize_message(
    payload: CategorizeRequest,
    llm: Llama = Depends(get_llm),
    cache: CategoryCache = Depends(get_category_cache),
) -> CategorizeResponse:
    try:
        category = categorize_description(
            payload.description, llm=llm, category_cache=cache
        )
        return CategorizeResponse(category=category, success=True)
    except Exception as error:
        logger.exception("Failed to categorize description")
        return CategorizeResponse(category="", success=False, error=str(error))


@router.get("/debtors", response_model=DebtorsResponse)
def get_debtors(
    sheets_client: gspread.Client = Depends(get_sheets_client),
) -> DebtorsResponse:
    try:
        month, debtors = list_debtors(sheets_client)
        groups = [
            DebtorGroup(
                name=debtor.name,
                total=format_amount(debtor.total),
                items=[
                    DebtorItem(description=desc, amount=amount)
                    for desc, amount in debtor.items
                ],
            )
            for debtor in debtors
        ]
        return DebtorsResponse(month=month, debtors=groups, success=True)
    except Exception as error:
        logger.exception("Failed to read debtors")
        return DebtorsResponse(success=False, error=str(error))
