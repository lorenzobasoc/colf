import os
import pytest
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.infrastructure.agents.agents_runner import run_agent
from src.infrastructure.agents.agents_utils import build_string_content
from src.modules.expenses.agents.expense_agents import message_expense_agent

class TestExpenseAgent:
    """Test class for expense agent functionality."""
    
    @pytest.mark.asyncio
    async def test_manual(self):
        """Manual test to check agent response."""
        user_input = build_string_content("corda arrampicata 20 euro")
        
        res = await run_agent(agent=message_expense_agent, content=user_input)

        print(res)

    