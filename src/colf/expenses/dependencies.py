import gspread
from fastapi import Request
from llama_cpp import Llama


def get_llm(request: Request) -> Llama:
    return request.app.state.llm


def get_sheets_client(request: Request) -> gspread.Client:
    return request.app.state.sheets_client
