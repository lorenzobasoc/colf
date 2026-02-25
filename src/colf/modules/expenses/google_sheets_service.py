import os
import logging
from datetime import datetime
from collections import defaultdict
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        self.service_account_path = os.getenv('SERVICE_ACCOUNT_PATH')
        # SPREADSHEET_ID is no longer static, specific sheet depends on year
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.readonly' 
        ]
        self._creds = None
        self._sheets_service = None
        self._drive_service = None

        if not self.service_account_path:
            logger.error("SERVICE_ACCOUNT_PATH not found in environment variables")
            raise ValueError("SERVICE_ACCOUNT_PATH not found")

    def _get_creds(self):
        if not self._creds:
            try:
                self._creds = service_account.Credentials.from_service_account_file(
                    self.service_account_path, scopes=self.scopes
                )
            except Exception as e:
                logger.error(f"Failed to load credentials: {e}")
                raise
        return self._creds

    def _get_sheets_service(self):
        if not self._sheets_service:
            self._sheets_service = build('sheets', 'v4', credentials=self._get_creds())
        return self._sheets_service

    def _get_drive_service(self):
        if not self._drive_service:
            self._drive_service = build('drive', 'v3', credentials=self._get_creds())
        return self._drive_service

    def _find_spreadsheet_for_year(self, year: int) -> str:
        """Finds the spreadsheet ID for the given year (e.g. 'Spese 2025')."""
        drive = self._get_drive_service()
        query = f"mimeType = 'application/vnd.google-apps.spreadsheet' and name contains 'Spese {year}' and trashed = false"
        
        try:
            results = drive.files().list(q=query, pageSize=1, fields="files(id, name)").execute()
            files = results.get('files', [])
            if not files:
                logger.error(f"No spreadsheet found for 'Spese {year}'")
                raise ValueError(f"Spreadsheet 'Spese {year}' not found")
            
            spreadsheet = files[0]
            logger.info(f"Found spreadsheet: {spreadsheet['name']} ({spreadsheet['id']})")
            return spreadsheet['id']
        except HttpError as e:
            logger.error(f"Drive API error: {e}")
            raise

    def _calculate_first_empty_row(self, service, spreadsheet_id, sheet_name) -> int:
        """Calculates the first empty row by counting existing rows."""
        try:
            # Read columns A-D to check for content
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1:D",
                valueRenderOption="UNFORMATTED_VALUE" 
            ).execute()
            
            values = result.get('values', [])
            num_rows = len(values)
            # The prompt says: First empty row = total rows + 1
            # If values is empty (0 rows), it creates header effectively at row 1? 
            # Prompt assumes header exists. If 10 rows (1 header + 9 data), next is 11.
            return num_rows + 1
        except HttpError as e:
            logger.error(f"Error calculating empty row: {e}")
            raise

    def add_expense(self, expense_data: dict):
        """
        Adds expenses to the correct Google Sheet based on Year and Month.
        Expects keys: 'spese' containing list of expense dicts.
        Dict keys from prompted LLM: 'giorno', 'mese', 'categoria', 'nome', 'importo'.
        """
        expenses = expense_data.get('spese', [])
        if not expenses:
            if isinstance(expense_data, list):
                expenses = expense_data
            else:
                 logger.warning("No expenses found in data")
                 return
        
        # Group by Month and Year
        # The extraction only gives Month name and Day. We assume Year is current year.
        # Ideally we should parse "Mese" to handle year boundary if needed, but for now defaulting to current year.
        current_year = datetime.now().year
        
        expenses_by_month = defaultdict(list)
        
        for exp in expenses:
            month = exp.get('mese')
            if not month:
                logger.warning(f"Expense missing month: {exp}, skipping")
                continue
            # Capitalize month just in case
            month = month.capitalize()
            expenses_by_month[month].append(exp)

        service = self._get_sheets_service()

        results = []
        for month, month_expenses in expenses_by_month.items():
            try:
                # 1. Identify Spreadsheet
                spreadsheet_id = self._find_spreadsheet_for_year(current_year)
                
                # 2. Verify Sheet exists (Optional but good practice based on prompt "Se il foglio non esiste, segnala errore")
                # We interpret "verify sheet structure" implies checking it exists.
                # Just proceeding to read it will fail if it doesn't exist.
                
                # 3. Calculate first empty row
                first_empty_row = self._calculate_first_empty_row(service, spreadsheet_id, month)
                
                # 4. Prepare data
                values = []
                for exp in month_expenses:
                    # Order: [Data, Descrizione, Tipologia, Importo]
                    # Data should be full date? Prompt says "JSON 'data' -> Colonna A (Data)". 
                    # Prompt input example: "data": "10". Output array example: ["10", ...].
                    # So we just put the day number? Or currently standard "10".
                    # Prompt Step 4.1: "Colonna A = data". 
                    # Prompt Step Example: ["10", "Pizza", ...]
                    # So we stick to what LLM gives (day number).
                    
                    row = [
                        str(exp.get('giorno', '')),
                        exp.get('nome', ''),
                        exp.get('categoria', ''),
                        str(exp.get('importo', '')).replace('.', ',') # Ensure comma for Italian locale
                    ]
                    values.append(row)
                
                # 5. Calculate Range
                num_expenses = len(values)
                start_row = first_empty_row
                end_row = start_row + num_expenses - 1
                range_name = f"'{month}'!A{start_row}:D{end_row}"
                
                # 6. Update Cells
                body = {'values': values}
                result = service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
                
                logger.info(f"Added {num_expenses} expenses to {month} (Range: {range_name})")
                results.append(result)

            except Exception as e:
                logger.error(f"Failed to process expenses for {month}: {e}")
                raise e # Or continue to next month? Raising to let caller know.

        return results
