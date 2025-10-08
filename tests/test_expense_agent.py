import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv
import sys
import os
from src.infrastructure.agents.agents_infrastructure import build_string_content, run_agent
from src.modules.expenses.agent.expense_agent import expense_agent

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestExpenseAgent:
    """Test class for expense agent functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup method run before each test."""
        # Ensure environment variables are loaded
        load_dotenv()
    
    def test_agent_initialization(self):
        """Test that the expense agent is properly initialized."""
        assert expense_agent is not None
        assert expense_agent.name == "expense_agent"
        assert expense_agent.model == os.getenv('LLM_MODEL')
        assert "classify expenses" in expense_agent.description.lower()
    
    @pytest.mark.asyncio
    async def test_manual(self):
        """Manual test to check agent response."""
        user_input = build_string_content("Classify the following expense: 'Lunch with client for $45'")
        
        res = await run_agent(agent=expense_agent, content=user_input)

        print("Agent Response:", res)

    