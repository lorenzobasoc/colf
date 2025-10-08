import os
from dotenv import load_dotenv
from google.adk.agents import Agent

load_dotenv()

expense_agent = Agent(
    name="expense_agent",
    model=os.getenv('LLM_MODEL'),
    description=(
        "Agent to classify expenses from natural lenguage."
    ),
    instruction=(
        "I can answer your questions about the time and weather in a city."
    ),
    tools=[],
)
