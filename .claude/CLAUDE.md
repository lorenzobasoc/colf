E' un progetto python che usa uv come package manager, fastapi e Google ADK per la gestione una architettura di agenti.

comando per eseguire i test:
uv run pytest tests/ -vs

comando per eseguire l'api
uv run uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload