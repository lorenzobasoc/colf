import logging
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .config import get_settings
from .expenses.category_cache import CategoryCache
from .expenses.llm.categorizer import load_llm
from .expenses.router import router as expenses_router
from .expenses.sheets import create_sheets_client, read_categorized_descriptions
from .invoices.repository import create_tables
from .invoices.router import api_router as invoices_api_router
from .invoices.router import ui_router as invoices_ui_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.llm = load_llm(settings)
    app.state.sheets_client = create_sheets_client(settings)
    app.state.category_cache = CategoryCache(
        lambda: read_categorized_descriptions(app.state.sheets_client)
    )

    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.invoices_xml_dir.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(settings.sqlite_path))
    db.row_factory = aiosqlite.Row
    await create_tables(db)
    app.state.db = db

    yield

    await db.close()


app = FastAPI(title="Colf API", version="1.0.0", lifespan=lifespan)
app.include_router(expenses_router)
app.include_router(invoices_api_router)
app.include_router(invoices_ui_router)


@app.get("/", response_class=HTMLResponse)
def read_root() -> str:
    return """
    <html>
        <head><title>Colf API</title></head>
        <body>
            <h1>Welcome to Colf API</h1>
            <p><a href="/ui/invoices">Fatture</a> | <a href="/ui/clients">Clienti</a></p>
        </body>
    </html>
    """


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "message": "API is running"}
