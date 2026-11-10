import json
from types import SimpleNamespace
import pytest
from colf.notion_sync.sheets import SheetStore, bea_rows


class Worksheet:
    def __init__(self, title, identifier, values=None):
        self.title, self.id = title, identifier
        self.row_count, self.col_count = 100, 10
        self.values = values or []
    def get(self, range_name, **kwargs):
        if range_name == 'A:D':
            return [getattr(self, 'headers', ['Data','Descrizione','Tipologia','Importo']), [8, 'vecchia', 'Bar', 1]]
        return self.values


class Spreadsheet:
    def __init__(self, bea=None):
        self.month = Worksheet('Novembre', 1, bea)
        self.ledger = Worksheet('_colf_imports', 2)
        self.calls = []
    def worksheets(self):
        return [self.month, self.ledger]
    def fetch_sheet_metadata(self, params=None):
        fmt = getattr(self, 'money_format', None)
        cell = {'userEnteredFormat': {'numberFormat': fmt}} if fmt else {}
        return {'sheets':[{'data':[{'rowData':[{'values':[cell]}]}]}]}
    def batch_update(self, body):
        self.calls.append(body)


def item(identifier='id'):
    return {'id':identifier, 'date':'2026-11-09', 'description':'Cena', 'category':'🍔 Cibo fuori',
            'personal_eur':'1.75', 'bea_eur':'1.76', 'shared':True, 'currency':'THB',
            'amount':'130', 'rate':'0.027', 'rate_date':'2026-11-09'}


def test_bea_layout_and_preservation():
    assert bea_rows([[8], ['pizza', 2]], [item()]) == [[8, ''], ['pizza', 2], ['', ''], [9, ''], ['Cena', 1.76]]
    with pytest.raises(ValueError):
        bea_rows([['Bea', 'Cena', '10']], [item()])


def test_single_atomic_request_main_bea_and_ledger():
    spreadsheet = Spreadsheet()
    store = SheetStore(spreadsheet)
    store.commit_imports([item()])
    assert len(spreadsheet.calls) == 1
    updates = [r['updateCells'] for r in spreadsheet.calls[0]['requests'] if 'updateCells' in r]
    assert len(updates) == 3
    main, bea, ledger = updates
    assert main['start'] == {'sheetId': 1, 'rowIndex': 2, 'columnIndex': 0}
    assert main['rows'][0]['values'][3]['userEnteredValue'] == {'numberValue': 1.75}
    assert bea['start']['rowIndex'] == 22
    assert bea['rows'][1]['values'][1]['userEnteredValue'] == {'numberValue': 1.76}
    record = json.loads(ledger['rows'][0]['values'][1]['userEnteredValue']['stringValue'])
    assert record['id'] == 'id'


def test_invalid_legacy_layout_never_writes():
    spreadsheet = Spreadsheet([['Bea','Pizza',10]])
    with pytest.raises(ValueError):
        SheetStore(spreadsheet).commit_imports([item()])
    assert spreadsheet.calls == []


def test_existing_sheet_header_whitespace_is_preserved():
    spreadsheet = Spreadsheet()
    spreadsheet.month.headers = ['Data', 'Descrizione', 'Tipologia', ' Importo']
    SheetStore(spreadsheet).commit_imports([item()])
    updates = [r['updateCells'] for r in spreadsheet.calls[0]['requests'] if 'updateCells' in r]
    assert updates[0]['start']['rowIndex'] == 2


def test_bea_appends_even_when_new_day_is_earlier():
    existing = [[10], ['pizza', 2]]
    assert bea_rows(existing, [item()]) == [[10, ''], ['pizza', 2], ['', ''], [9, ''], ['Cena', 1.76]]
    assert existing == [[10], ['pizza', 2]]


def test_bea_appends_to_last_day_without_rewriting_earlier_groups():
    existing = [[9], ['pranzo', 4], ['', ''], [10], ['pizza', 2]]
    expense = {**item(), 'date':'2026-11-10'}
    assert bea_rows(existing, [expense]) == [[9, ''], ['pranzo', 4], ['', ''], [10, ''], ['pizza', 2], ['Cena', 1.76]]


def test_google_bea_write_targets_only_new_tail_rows():
    spreadsheet = Spreadsheet([[9], ['pizza', 2]])
    SheetStore(spreadsheet).commit_imports([item()])
    updates = [r['updateCells'] for r in spreadsheet.calls[0]['requests'] if 'updateCells' in r]
    assert updates[1]['start'] == {'sheetId':1, 'rowIndex':24, 'columnIndex':6}
    assert len(updates[1]['rows']) == 1


def test_main_and_bea_amounts_have_euro_currency_format():
    spreadsheet = Spreadsheet()
    SheetStore(spreadsheet).commit_imports([item()])
    updates = [r['updateCells'] for r in spreadsheet.calls[0]['requests'] if 'updateCells' in r]
    for cell in (updates[0]['rows'][0]['values'][3], updates[1]['rows'][1]['values'][1]):
        fmt = cell['userEnteredFormat']['numberFormat']
        assert fmt['type'] == 'CURRENCY'
        assert '€' in fmt['pattern']


def test_money_cells_are_right_aligned_without_changing_other_alignment():
    spreadsheet = Spreadsheet()
    SheetStore(spreadsheet).commit_imports([item()])
    alignments = [r['repeatCell'] for r in spreadsheet.calls[0]['requests'] if 'repeatCell' in r]
    assert len(alignments) == 2
    assert [a['range'] for a in alignments] == [
        {'sheetId':1,'startRowIndex':2,'endRowIndex':3,'startColumnIndex':3,'endColumnIndex':4},
        {'sheetId':1,'startRowIndex':22,'endRowIndex':24,'startColumnIndex':7,'endColumnIndex':8}]
    assert all(a['cell']['userEnteredFormat']['horizontalAlignment'] == 'RIGHT' for a in alignments)
    assert all(a['fields'] == 'userEnteredFormat.horizontalAlignment' for a in alignments)


def test_amounts_inherit_existing_accounting_format_instead_of_replacing_it():
    spreadsheet = Spreadsheet()
    spreadsheet.money_format = {'type':'NUMBER','pattern':'_-* #,##0.00" €"_-'}
    SheetStore(spreadsheet).commit_imports([item()])
    updates = [r['updateCells'] for r in spreadsheet.calls[0]['requests'] if 'updateCells' in r]
    for cell in (updates[0]['rows'][0]['values'][3], updates[1]['rows'][1]['values'][1]):
        assert cell['userEnteredFormat']['numberFormat'] == spreadsheet.money_format
