import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import get_settings
from .expenses.llm.categorizer import load_llm
from .expenses.router import router as expenses_router
from .expenses.sheets import create_sheets_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.llm = load_llm(settings)
    app.state.sheets_client = create_sheets_client(settings)
    yield


app = FastAPI(title="Colf API", version="1.0.0", lifespan=lifespan)
app.include_router(expenses_router)


@app.get("/", response_class=HTMLResponse)
def read_root() -> str:
    return """
    <html>
        <head><title>Colf API</title></head>
        <body>
            <h1>Welcome to Colf API</h1>
            <p>Your FastAPI application is running!</p>
        </body>
    </html>
    """


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "message": "API is running"}
