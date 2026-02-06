from src.colf.infrastructure.agents.agents_runner import run_agent
from src.colf.infrastructure.agents.agents_utils import build_string_content
from src.colf.modules.expenses.agents.expense_agents import message_workflow_agent
from google.adk.sessions import InMemorySessionService
from agentops.sdk.decorators import session

APP_NAME = "my_app"
USER_ID = "my_user"
SESSION_ID = "session_id"

@session
class ExpenseService:
    async def message_expense_workflow(self, message: str) -> str:
        message_content = build_string_content(message)

        session_service = InMemorySessionService()
        session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

        response = await run_agent(agent=message_workflow_agent, content=message_content, session=session, session_service=session_service)

        return response
    