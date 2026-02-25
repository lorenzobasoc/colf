from fastapi import APIRouter, Depends
from .expense_agent_requests import MessageExpenseAgentRequest, MessageExpenseAgentResponse
from ..expense_service import ExpenseService

from functools import lru_cache

@lru_cache()
def get_expense_service() -> ExpenseService:
    return ExpenseService()

class ExpenseAgentController:
    def __init__(self):
        self.router = APIRouter(prefix="/api/agents/expenses", tags=["expenses"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.post("/message", response_model=MessageExpenseAgentResponse)
        async def send_message_expenses(request: MessageExpenseAgentRequest, expense_service: ExpenseService = Depends(get_expense_service)):
            try:
                response = await expense_service.message_expense_workflow(request.message)
                return MessageExpenseAgentResponse(response=response, success=True)
            except Exception as e:
                return MessageExpenseAgentResponse(response="", success=False, error=str(e))

    def get_router(self) -> APIRouter:
        return self.router