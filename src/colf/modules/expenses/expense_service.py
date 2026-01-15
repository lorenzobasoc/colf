from ...infrastructure.agents.agents_runner import run_agent
from ...infrastructure.agents.agents_utils import build_string_content, clean_agent_response
from .parlant.expense_agent import expense_agent

class ExpenseService:
    async def message_expense_workflow(self, message: str) -> str:
        agent = await expense_agent()
    
        return response
    