from pydantic import BaseModel
from typing import Optional

class MessageExpenseAgentRequest(BaseModel):
    message: str

class MessageExpenseAgentResponse(BaseModel):
    response: str
    success: bool
    error: Optional[str] = None