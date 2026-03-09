import logging
from ...infrastructure.llm.local_llm_service import LocalLLMService
from ...infrastructure.google_sheets.google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

class ExpenseService:
    def __init__(self):
        self.llm_service = LocalLLMService()
        self.sheets_service = GoogleSheetsService()

    async def message_expense_workflow(self, message: str) -> str:
        logger.info(f"Processing message: {message}")
        
        categorized_data = self.llm_service.categorize_expense(message)
        logger.debug(f"Categorized data: {categorized_data}")

        self.sheets_service.add_expense(categorized_data)            