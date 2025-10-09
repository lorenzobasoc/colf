import os
import pytest
import sys
from dotenv import load_dotenv

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.infrastructure.agents.agents_runner import run_agent
from src.infrastructure.agents.agents_utils import build_string_content
from src.modules.expenses.agents.expense_agents import chat_expense_agent

class TestExpenseAgent:
    """Test class for expense agent functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method run before each test."""
        # Ensure environment variables are loaded
        load_dotenv()
    
    def test_agent_initialization(self):
        """Test that the expense agent is properly initialized."""
        assert chat_expense_agent is not None
        assert chat_expense_agent.name == "chat_expense_agent"
        assert chat_expense_agent.model == os.getenv('LLM_MODEL')
        assert "classify expenses" in chat_expense_agent.description.lower()
    
    @pytest.mark.asyncio
    async def test_manual(self):
        """Manual test to check agent response."""
        user_input = build_string_content("metro 2 euro e 20")
        
        res = await run_agent(agent=chat_expense_agent, content=user_input)

        print("Agent Response:", res)

    