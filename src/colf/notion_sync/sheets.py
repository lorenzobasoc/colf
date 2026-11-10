"""Atomic writes to the existing monthly sheet and a hidden import ledger."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
import json
from ..expenses.constants import ITALIAN_MONTHS, SHEET_HEADERS

LEDGER = '_colf_imports'


def bea_rows(existing: list[list], items: list[dict]) -> list[list]:
    result = []
    current = None
    for row in existing:
        first, second, third = (list(row) + ['', '', ''])[:3]
        if third not in ('', None):
            raise ValueError('Blocco debitori legacy G:I: migrazione richiesta')
        if first in ('', None) and second in ('', None):
            result.append(['', ''])
        elif second in ('', None) and str(first).isdigit() and 1 <= int(first) <= 31:
            current = int(first)
            result.append([current, ''])
        elif current is not None and first not in ('', None):
            value = Decimal(str(second).replace(',', '.'))
            if not value.is_finite() or value < 0:
                raise ValueError('Importo Bea non valido')
            result.append([str(first), float(value)])
        else:
            raise ValueError('Layout Bea sconosciuto: atteso giorno e descrizione/importo')
    while result and result[-1] == ['', '']:
        result.pop()
    for item in items:
        if not item['shared']:
            continue
        day = date.fromisoformat(item['date']).day
        if not result or current != day:
            if result:
                result.append(['', ''])
            result.append([day, ''])
            current = day
        result.append([item['description'], float(item['bea_eur'])])
    return result


def _cell(value, *, money=False, money_format=None):
    if value == '' or value is None:
        return {}
    numeric = isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    result = {'userEnteredValue': {'numberValue': float(value)} if numeric else {'stringValue': str(value)}}
    if money:
        result['userEnteredFormat'] = {'numberFormat': money_format or {'type': 'CURRENCY', 'pattern': '#,##0.00" €"'}}
    return result


def _write(sheet_id, row, col, values, money_columns=(), *, money_format=None):
    return {'updateCells': {'start': {'sheetId': sheet_id, 'rowIndex': row, 'columnIndex': col},
        'rows': [{'values': [_cell(value, money=i in money_columns, money_format=money_format) for i, value in enumerate(values_row)]}
                 for values_row in values], 'fields': 'userEnteredValue,userEnteredFormat.numberFormat'}}


def _right_align(sheet_id, row, end_row, column):
    return {'repeatCell': {'range': {'sheetId': sheet_id, 'startRowIndex': row,
        'endRowIndex': end_row, 'startColumnIndex': column, 'endColumnIndex': column + 1},
        'cell': {'userEnteredFormat': {'horizontalAlignment': 'RIGHT'}},
        'fields': 'userEnteredFormat.horizontalAlignment'}}


class SheetStore:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet

    def load_imports(self) -> dict[str, dict]:
        ledger = next((ws for ws in self.spreadsheet.worksheets() if ws.title == LEDGER), None)
        if ledger is None:
            return {}
        result = {}
        for row in ledger.get('A:B'):
            if not row or not row[0]:
                continue
            if len(row) < 2:
                raise ValueError('Registro importazioni incompleto')
            record = json.loads(row[1])
            if record['id'] != row[0] or row[0] in result:
                raise ValueError('Registro importazioni non valido')
            result[row[0]] = record
        return result

    def _money_format(self, worksheet, source_row):
        if worksheet.row_count < source_row or worksheet.col_count < 4:
            return None
        metadata = self.spreadsheet.fetch_sheet_metadata(params={
            'includeGridData': 'true', 'ranges': f"'{worksheet.title}'!D{source_row}",
            'fields': 'sheets(data(rowData(values(userEnteredFormat(numberFormat)))))'})
        for sheet in metadata.get('sheets', []):
            for data in sheet.get('data', []):
                for row in data.get('rowData', []):
                    for cell in row.get('values', []):
                        fmt = cell.get('userEnteredFormat', {}).get('numberFormat', {})
                        if '€' in fmt.get('pattern', ''):
                            return fmt
        return None

    def commit_imports(self, items: list[dict]) -> None:
        if not items:
            return
        known = self.load_imports()
        if any(item['id'] in known for item in items):
            raise ValueError('Importazione già registrata; rileggere registro prima di riprovare')
        worksheets = self.spreadsheet.worksheets()
        ledger = next((ws for ws in worksheets if ws.title == LEDGER), None)
        ledger_id = ledger.id if ledger else max(ws.id for ws in worksheets) + 1
        requests = []
        if ledger is None:
            requests.append({'addSheet': {'properties': {'sheetId': ledger_id, 'title': LEDGER,
                'hidden': True, 'gridProperties': {'rowCount': max(1000, len(items)), 'columnCount': 2}}}})
        elif ledger.row_count < len(known) + len(items):
            requests.append({'appendDimension': {'sheetId': ledger.id, 'dimension': 'ROWS',
                'length': len(known) + len(items) - ledger.row_count}})
        grouped = defaultdict(list)
        for item in items:
            grouped[date.fromisoformat(item['date']).month].append(item)
        for month, group in grouped.items():
            worksheet = next((ws for ws in worksheets if ws.title == ITALIAN_MONTHS[month - 1]), None)
            if worksheet is None:
                raise ValueError(f'Tab mensile mancante: {ITALIAN_MONTHS[month - 1]}')
            existing_main = list(worksheet.get('A:D', value_render_option='UNFORMATTED_VALUE'))
            while existing_main and not any(value not in ('', None) for value in existing_main[-1]):
                existing_main.pop()
            if existing_main and [str(value).strip() for value in existing_main[0][:4]] != SHEET_HEADERS:
                raise ValueError('Intestazioni tabella principale inattese')
            main_row = len(existing_main) if existing_main else 0
            main = ([] if existing_main else [SHEET_HEADERS]) + [[date.fromisoformat(i['date']).day,
                i['description'], i['category'], Decimal(i['personal_eur'])] for i in group]
            existing_bea = list(worksheet.get('G23:I', value_render_option='UNFORMATTED_VALUE'))
            while existing_bea and not any(value not in ('', None) for value in existing_bea[-1]):
                existing_bea.pop()
            shared = any(i['shared'] for i in group)
            # Validate the new layout even when this batch has no shared expenses.
            updated_bea = bea_rows(existing_bea, group)
            money_format = self._money_format(worksheet, max(2, main_row))
            needed = max(main_row + len(main), 22 + len(updated_bea))
            if needed > worksheet.row_count:
                requests.append({'appendDimension': {'sheetId': worksheet.id, 'dimension': 'ROWS',
                    'length': needed - worksheet.row_count}})
            if worksheet.col_count < 9:
                requests.append({'appendDimension': {'sheetId': worksheet.id, 'dimension': 'COLUMNS',
                    'length': 9 - worksheet.col_count}})
            requests.append(_write(worksheet.id, main_row, 0, main, (3,), money_format=money_format))
            requests.append(_right_align(worksheet.id, main_row, main_row + len(main), 3))
            if shared:
                tail = updated_bea[len(existing_bea):]
                requests.append(_write(worksheet.id, 22 + len(existing_bea), 6, tail, (1,), money_format=money_format))
                requests.append(_right_align(worksheet.id, 22 + len(existing_bea), 22 + len(updated_bea), 7))
        requests.append(_write(ledger_id, len(known), 0,
            [[item['id'], json.dumps(item, ensure_ascii=False, sort_keys=True)] for item in items]))
        # Never retry this request blindly: the next run reads the ledger first.
        self.spreadsheet.batch_update({'requests': requests})
