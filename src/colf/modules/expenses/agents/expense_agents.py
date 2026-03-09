import os
import logging
import agentops
from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents import Agent
from mcp import StdioServerParameters
from ....infrastructure.agents.agents_utils import read_prompt_file
from ....infrastructure.agents.general_tools import get_current_date
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools import agent_tool

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

load_dotenv()

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")
agentops.init(
    api_key=AGENTOPS_API_KEY,
    default_tags=['google adk']
)

env = {
    "SERVICE_ACCOUNT_PATH": os.getenv('SERVICE_ACCOUNT_PATH'),
    "DRIVE_FOLDER_ID": os.getenv('DRIVE_FOLDER_ID')
}

expense_message_categorizer_agent = Agent(
    name="expense_message_categorizer_agent",
    model=os.getenv('LLM_MODEL'),
    description=("Agent to classify expenses from natural language from Telegram messagges."),
    instruction=read_prompt_file(Path(__file__).parent / "prompts" / "expense_message_categorizer_agent_prompt.md"),
    tools=[ get_current_date ],
    output_key="expense_classification"
)

google_sheets_expense_adder_agent = Agent(
    name="google_sheets_expense_adder_agent",
    model=os.getenv('LLM_MODEL'),
    description=("Agent to add classified expenses to a Google Sheets spreadsheet"),
    instruction=read_prompt_file(Path(__file__).parent / "prompts" / "google_sheets_expense_adder_agent_prompt.md"),
    tools=[
        McpToolset(
            connection_params=StdioServerParameters(
                command='mcp-google-sheets',
                args=[],
                env=env
            ),
        )
    ],
)

tool1 = agent_tool.AgentTool(agent=expense_message_categorizer_agent)
tool2 = agent_tool.AgentTool(agent=google_sheets_expense_adder_agent)

message_workflow_agent = Agent(
    name="message_workflow_agent",
    description="Agente coordinatore responsabile della classificazione e dell’inserimento delle spese in Google Sheets.",
    model=os.getenv('LLM_MODEL'),
    instruction=(read_prompt_file(Path(__file__).parent / "prompts" / "message_workflow_agent_prompt.md")),
    tools=[tool1, tool2]
)
