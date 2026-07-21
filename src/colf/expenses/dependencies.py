import gspread
from fastapi import Request
from llama_cpp import Llama

from .category_cache import CategoryCache


def get_llm(request: Request) -> Llama:
    return request.app.state.llm


def get_sheets_client(request: Request) -> gspread.Client:
    return request.app.state.sheets_client


def get_category_cache(request: Request) -> CategoryCache:
    return request.app.state.category_cache
