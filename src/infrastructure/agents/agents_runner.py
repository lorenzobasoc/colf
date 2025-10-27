from google.adk.runners import Runner
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService, Session

APP_NAME = "my_app"
USER_ID = "my_user"
SESSION_ID = "session_id"

async def run_agent(agent: Agent, content: str, session: Session = None, session_service: InMemorySessionService = None) -> str:
    # TODO: Use a persistent session service (DatabaseSessionService, VertexAiSessionService)
    if session_service is None:
        session_service = InMemorySessionService()

    if session is None:
        session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        if event.is_final_response():
            final_response = event.content.parts[0].text
            return final_response
        