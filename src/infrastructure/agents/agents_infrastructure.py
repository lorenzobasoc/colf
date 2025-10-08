from google.adk.runners import Runner
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.genai import types

APP_NAME = "my_app"
USER_ID = "my_user"

async def run_agent(agent: Agent, content: str) -> str:
    # TODO: Use a persistent session service (DatabaseSessionService, VertexAiSessionService)
    # if session_service is None:
    #     session_service = InMemorySessionService()

    # if session_id is None:
    #     session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    #     session_id = session.id

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={}
    )

    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=content):
        if event.is_final_response():
            final_response = event.content.parts[0].text
            return final_response
        
def build_string_content(prompt):
    return types.Content(role="user", parts=[types.Part(text=prompt)])