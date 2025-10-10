import os
import pytest
import sys
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService, Session

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.infrastructure.agents.agents_runner import run_agent
from src.infrastructure.agents.agents_utils import build_string_content
from src.modules.expenses.agents.expense_agents import message_expense_agent, google_sheets_expense_adder_agent

APP_NAME = "my_app"
USER_ID = "my_user"

class TestExpenseAgent:
    """Test class for expense agent functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        load_dotenv()
    
    # @pytest.mark.asyncio
    # async def test_message_expenses_categorizer(self):
    #     """Manual test to check agent response."""
    #     user_input = build_string_content("corda arrampicata 20 euro")
        
    #     res = await run_agent(agent=message_expense_agent, content=user_input)

    #     print(res)

    @pytest.mark.asyncio
    async def test_google_sheets_mcp(self):
        """Manual test to check agent response."""
        user_input = build_string_content("""{"spese": [{"categoria": "🕺 Festa/Eventi", "nome": "Rave", "importo": "109,99", "data": 31, "mese": "Agosto"}]}""")
        
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            state={'current_year': '2025'}
        )

        res = await run_agent(agent=google_sheets_expense_adder_agent, content=user_input, session=session, session_service=session_service)

        print(res)

    