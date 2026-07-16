from pydantic import BaseModel


class MessageRequest(BaseModel):
    message: str


class ExpenseDraft(BaseModel):
    day: int
    month: str
    description: str
    category: str
    amount: str
    total_amount: str | None = None
    participants: list[str] = []


class CategoryOption(BaseModel):
    key: str
    label: str


class ParseResponse(BaseModel):
    draft: ExpenseDraft | None = None
    categories: list[CategoryOption] = []
    success: bool
    error: str | None = None


class CommitResponse(BaseModel):
    response: str
    success: bool
    error: str | None = None


class NotificationRequest(BaseModel):
    title: str
    text: str
    source: str | None = None
    posted_at: str | None = None


class ParseNotificationResponse(BaseModel):
    draft: ExpenseDraft | None = None
    categories: list[CategoryOption] = []
    needs_description: bool = False
    success: bool
    error: str | None = None


class CategorizeRequest(BaseModel):
    description: str


class CategorizeResponse(BaseModel):
    category: str
    success: bool
    error: str | None = None
