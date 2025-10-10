import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from mcp import StdioServerParameters
from ....infrastructure.agents.agents_utils import read_prompt_file
from ....infrastructure.agents.general_tools import get_current_date
from google.adk.tools.mcp_tool import McpToolset

load_dotenv()

message_expense_agent = Agent(
    name="message_expense_agent",
    model=os.getenv('LLM_MODEL'),
    description=(
        "Agent to classify expenses from natural lenguage from Telegram messagges."
    ),
    instruction=read_prompt_file(os.path.join(os.path.dirname(__file__), "prompts", "message_expense_agent_prompt.md")),
    tools=[get_current_date],
)

env = {
    "SERVICE_ACCOUNT_PATH": os.getenv('SERVICE_ACCOUNT_PATH'),
    "DRIVE_FOLDER_ID": os.getenv('DRIVE_FOLDER_ID')
}

google_sheets_expense_adder_agent = Agent(
    name="google_sheets_expense_adder_agent",
    model=os.getenv('LLM_MODEL'),
    description=(
       # "Agent to add classified expenses to a Google Sheets spreadsheet using MCP."
       "Agente che estrae la lista degli spreadsheets"
    ),
    instruction=read_prompt_file(os.path.join(os.path.dirname(__file__), "prompts", "google_sheets_expense_adder_agent_prompt.md")),
    tools=[
        McpToolset(
            connection_params=StdioServerParameters(
                command='uvx',
                args=["mcp-google-sheets@latest"],
                env=env
            ),
            # tool_filter=['read_file', 'list_directory']
        )
    ],
)