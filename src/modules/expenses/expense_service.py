from src.infrastructure.agents.agents_runner import run_agent
from src.infrastructure.agents.agents_utils import build_string_content, clean_agent_response
from src.modules.expenses.agents.expense_agents import message_expense_agent

class ExpenseService:
    async def call_message_expense_agent(self, message: str) -> str:
        message_content = build_string_content(message)

        response = await run_agent(agent=message_expense_agent, content=message_content)

        cleaned_response = clean_agent_response(response)
        
        return cleaned_response
    