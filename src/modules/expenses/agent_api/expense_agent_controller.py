from fastapi import APIRouter, Depends
from src.modules.expenses.agent_api.expense_agent_requests import MessageExpenseAgentRequest, MessageExpenseAgentResponse
from src.modules.expenses.expense_service import ExpenseService

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
                response = await expense_service.call_message_expense_agent(request.message)
                return MessageExpenseAgentResponse(response=response, success=True)
            except Exception as e:
                return MessageExpenseAgentResponse(response="", success=False, error=str(e))

    def get_router(self) -> APIRouter:
        return self.router