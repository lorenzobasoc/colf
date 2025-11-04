from pyparsing import Optional

class MessageExpenseAgentResponse():
    response: str
    success: bool
    error: Optional[str] = None