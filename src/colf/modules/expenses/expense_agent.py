import os
import asyncio
import parlant.sdk as p
import logging
from dotenv import load_dotenv
from .expense_categories import categories
from .expense_agent_guidelines import add_guidelines
from .expense_agent_journeys import create_message_categorization_journey

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

env = {
    "SERVICE_ACCOUNT_PATH": os.getenv('SERVICE_ACCOUNT_PATH'),
    "DRIVE_FOLDER_ID": os.getenv('DRIVE_FOLDER_ID')
}

async def run_expense_agent():
    async with p.Server(port=8000, log_level=p.LogLevel.INFO) as server:
        agent = await server.create_agent(
            name="expense_agent",
            id="expenses",
            description="Agente che classifica le spese a partire da messaggi Telegram in linguaggio naturale e le aggiungere a un foglio Google Sheets.",
        )

        await agent.create_term(
            name="Categorie di spesa",
            description=f"Sono le categorie di Spesa Disponibili per la classificazione. Includono SEMPRE l'emoji associata: {categories()}",
            synonyms=["Categorie", "categorie"],
        )

        await add_guidelines(agent)

        await create_message_categorization_journey(agent)

        logger.info("Parlant server is running on port 8000. Press Ctrl+C to stop.")

        return agent




        




# google_sheets_expense_adder_agent = Agent(
#     name="google_sheets_expense_adder_agent",
#     model=os.getenv('LLM_MODEL'),
#     description=("Agent to add classified expenses to a Google Sheets spreadsheet"),
#     instruction=read_prompt_file(Path(__file__).parent / "prompts" / "google_sheets_expense_adder_agent_prompt.md"),
#     tools=[
#         McpToolset(
#             connection_params=StdioServerParameters(
#                 command='mcp-google-sheets',
#                 args=[],
#                 env=env
#             ),
#         )
#     ],
# )

# # Telegram messages workflow
# expense_message_categorizer_agent = Agent(
#     name="expense_message_categorizer_agent",
#     model=os.getenv('LLM_MODEL'),
#     description=("Agent to classify expenses from natural language from Telegram messagges."),
#     instruction=read_prompt_file(Path(__file__).parent / "prompts" / "expense_message_categorizer_agent_prompt.md"),
#     tools=[ get_current_date ],
#     output_key="expense_classification"
# )

# tool1 = agent_tool.AgentTool(agent=expense_message_categorizer_agent)
# tool2 = agent_tool.AgentTool(agent=google_sheets_expense_adder_agent)

# message_workflow_agent = Agent(
#     name="message_workflow_agent",
#     description="Agente coordinatore responsabile della classificazione e dell’inserimento delle spese in Google Sheets.",
#     model=os.getenv('LLM_MODEL'),
#     instruction=(read_prompt_file(Path(__file__).parent / "prompts" / "message_workflow_agent_prompt.md")),
#     tools=[tool1, tool2]
# )


# Notifications workflow