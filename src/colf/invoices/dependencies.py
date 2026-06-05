import aiosqlite
from fastapi import Request

from ..config import Settings, get_settings


def get_db(request: Request) -> aiosqlite.Connection:
    return request.app.state.db


def get_settings_dep(request: Request) -> Settings:
    return get_settings()
