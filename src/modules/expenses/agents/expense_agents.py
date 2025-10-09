import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from ....infrastructure.agents.agents_utils import read_prompt_file
from ....infrastructure.agents.general_tools import get_current_date

load_dotenv()

chat_expense_agent = Agent(
    name="chat_expense_agent",
    model=os.getenv('LLM_MODEL'),
    description=(
        "Agent to classify expenses from natural lenguage from Telegram messagges."
    ),
    instruction=read_prompt_file(os.path.join(os.path.dirname(__file__), "prompts", "chat_expense_agent_prompt.md")),
    tools=[get_current_date],
)
