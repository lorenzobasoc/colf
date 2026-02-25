import logging
from ...infrastructure.llm.local_llm_service import LocalLLMService
from ...infrastructure.google_sheets.google_sheets_service import GoogleSheetsService

logger = logging.getLogger(__name__)

class ExpenseService:
    def __init__(self):
        try:
            self.llm_service = LocalLLMService()
            self.sheets_service = GoogleSheetsService()
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            # We might want to raise here or handle gracefully, 
            # but raising ensures the app knows it's broken on startup/request.
            raise

    async def message_expense_workflow(self, message: str) -> str:
        try:
            logger.info(f"Processing message: {message}")
            
            # 1. Categorize using local LLM
            categorized_data = self.llm_service.categorize_expense(message)
            logger.debug(f"Categorized data: {categorized_data}")
            
            # The prompt is instructed to return {"spese": [...]}
            # We should handle potential malformed response or direct list.
            if isinstance(categorized_data, dict):
                expenses = categorized_data.get('spese', [])
            elif isinstance(categorized_data, list):
                expenses = categorized_data
            else:
                logger.warning("Unexpected data format from LLM.")
                expenses = []
            
            if not expenses:
                return "Nessuna spesa trovata"

            # 2. Add to Google Sheets
            # sheets_service.add_expense expects the full dict or list for flexibility, 
            # but our recent refactor expects the dict with 'spese' key or list.
            # We already extracted 'expenses' list above for validation.
            # Let's pass the dictionary if available to match the signature expectation best, 
            # or reconstruct it.
            
            if isinstance(categorized_data, dict) and 'spese' in categorized_data:
                self.sheets_service.add_expense(categorized_data)
            else:
                 self.sheets_service.add_expense({'spese': expenses})
            
            return f"Ho aggiunto {len(expenses)} spese al foglio Google."

        except Exception as e:
            logger.exception("Error in message_expense_workflow")
            return f"Si è verificato un errore: {e}"