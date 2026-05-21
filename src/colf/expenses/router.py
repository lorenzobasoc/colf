import logging

import gspread
from fastapi import APIRouter, Depends
from llama_cpp import Llama

from .dependencies import get_llm, get_sheets_client
from .schemas import MessageRequest, MessageResponse
from .service import record_expense

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents/expenses", tags=["expenses"])


@router.post("/message", response_model=MessageResponse)
def submit_expense_message(
    payload: MessageRequest,
    llm: Llama = Depends(get_llm),
    sheets_client: gspread.Client = Depends(get_sheets_client),
) -> MessageResponse:
    try:
        summary = record_expense(payload.message, llm=llm, sheets_client=sheets_client)
        return MessageResponse(response=summary, success=True)
    except Exception as error:
        logger.exception("Failed to record expense")
        return MessageResponse(response="", success=False, error=str(error))
