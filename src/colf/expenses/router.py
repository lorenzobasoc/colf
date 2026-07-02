import logging
from dataclasses import asdict

import gspread
from fastapi import APIRouter, Depends
from llama_cpp import Llama

from .constants import CATEGORIES
from .dependencies import get_llm, get_sheets_client
from .domain import Expense
from .schemas import (
    CategoryOption,
    CommitResponse,
    ExpenseDraft,
    MessageRequest,
    ParseResponse,
)
from .service import commit_expense, parse_expense

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents/expenses", tags=["expenses"])


def _category_options() -> list[CategoryOption]:
    return [CategoryOption(key=key, label=label) for key, label in CATEGORIES.items()]


@router.post("/parse", response_model=ParseResponse)
def parse_message(
    payload: MessageRequest,
    llm: Llama = Depends(get_llm),
) -> ParseResponse:
    try:
        expense = parse_expense(payload.message, llm=llm)
        draft = ExpenseDraft(**asdict(expense))
        return ParseResponse(draft=draft, categories=_category_options(), success=True)
    except Exception as error:
        logger.exception("Failed to parse expense")
        return ParseResponse(success=False, error=str(error))


@router.post("/commit", response_model=CommitResponse)
def commit_message(
    draft: ExpenseDraft,
    sheets_client: gspread.Client = Depends(get_sheets_client),
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
        summary = commit_expense(expense, sheets_client=sheets_client)
        return CommitResponse(response=summary, success=True)
    except Exception as error:
        logger.exception("Failed to commit expense")
        return CommitResponse(response="", success=False, error=str(error))
