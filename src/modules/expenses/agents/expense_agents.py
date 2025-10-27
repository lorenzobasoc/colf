import os
import sys
import logging
from pathlib import Path
import agentops
from dotenv import load_dotenv
from google.adk.agents import Agent, SequentialAgent, ParallelAgent
from mcp import StdioServerParameters
from infrastructure.agents.agents_utils import read_prompt_file
from infrastructure.agents.general_tools import get_current_date
from google.adk.tools.mcp_tool import McpToolset

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

google_sheets_expense_adder_agent = Agent(
    name="google_sheets_expense_adder_agent",
    model=os.getenv('LLM_MODEL'),
    description=("Agent to add classified expenses to a Google Sheets spreadsheet"),
    instruction=read_prompt_file(Path(__file__).parent / "prompts" / "google_sheets_expense_adder_agent_prompt.md"),
    tools=[
        McpToolset(
            connection_params=StdioServerParameters(
                command='uvx',
                args=["mcp-google-sheets@latest"],
                env=env
            ),
        )
    ],
)

# Telegram messages workflow
expense_message_categorizer_agent = Agent(
    name="expense_message_categorizer_agent",
    model=os.getenv('LLM_MODEL'),
    description=("Agent to classify expenses from natural language from Telegram messagges."),
    instruction=read_prompt_file(Path(__file__).parent / "prompts" / "message_expense_agent_prompt.md"),
    tools=[ get_current_date ],
    output_key="expense_classification"
)

message_workflow_agent = Agent(
    name="message_workflow_agent",
    description="Agente coordinatore responsabile della classificazione e dell’inserimento delle spese in Google Sheets.",
    model=os.getenv('LLM_MODEL'),
    instruction=(
        "Sei un agente di coordinamento del workflow, incaricato di orchestrare due sotto-agenti specializzati: "
        "1) **expense_message_categorizer_agent**, responsabile dell’analisi e classificazione dei messaggi di spesa in linguaggio naturale, "
        "e 2) **google_sheets_expense_adder_agent**, responsabile dell’inserimento delle spese classificate in un foglio Google Sheets. "
        "Il tuo compito principale è garantire che il flusso venga eseguito **completamente e in sequenza**, senza saltare alcuna fase. "
        "\n\n"
        "Segui rigorosamente il seguente processo:\n"
        "- **Fase 1:** invoca **expense_message_categorizer_agent** e attendi il suo output strutturato di classificazione. "
        "Verifica che l’output contenga tutte le informazioni necessarie (ad esempio: categoria, importo, data, descrizione).\n"
        "- **Fase 2:** una volta ottenuta la classificazione, invoca immediatamente **google_sheets_expense_adder_agent**, "
        "passandogli l’output strutturato della fase precedente per registrare correttamente la spesa su Google Sheets.\n\n"
        "Devi **obbligatoriamente** invocare entrambi i sotto-agenti in quest’ordine preciso, garantendo coerenza e correttezza dei dati "
        "tra la fase di classificazione e quella di inserimento. Non è consentito saltare, unire o eseguire in parallelo le fasi. "
        "Alla fine del workflow, restituisci gli output di entrambi i sotto-agenti, indicando chiaramente a quale fase appartiene ciascun risultato."
    ),
    sub_agents=[google_sheets_expense_adder_agent, expense_message_categorizer_agent ]
)

root_agent = message_workflow_agent

# Notifications workflow