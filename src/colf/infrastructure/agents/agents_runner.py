import asyncio
import time
from google.adk.runners import Runner
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService, Session

APP_NAME = "my_app"
USER_ID = "my_user"
SESSION_ID = "session_id"

async def run_agent(agent: Agent, content: str, session: Session = None, session_service: InMemorySessionService = None) -> str:
    """Run an agent with exponential retry for overloaded model responses."""
    max_retries = 3
    base_delay = 1 # in seconds
    
    for attempt in range(max_retries + 1):
        try:
            # TODO: Use a persistent session service (DatabaseSessionService, VertexAiSessionService)
            if session_service is None:
                session_service = InMemorySessionService()

            if session is None:
                session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

            runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

            async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
                if event.is_final_response():
                    final_response = event.content.parts[0].text
                    
                    if "The model is overloaded" in final_response:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            print(f"Model overloaded, retrying in {delay} seconds (attempt {attempt + 1}/{max_retries + 1})")
                            await asyncio.sleep(delay)
                            break
                        else:
                            return final_response
                    else:
                        return final_response
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"Error occurred: {e}, retrying in {delay} seconds (attempt {attempt + 1}/{max_retries + 1})")
                await asyncio.sleep(delay)
            else:
                raise e
    
    raise Exception("Failed to get response after all retry attempts")
        