from datetime import date
from decimal import Decimal
import pytest
from colf.notion_sync.model import SourceLine
from colf.notion_sync.conversion import Rate
from colf.notion_sync.run import Journal, sync_page


class Notion:
    def __init__(self):
        self.text = 'Valuta: EUR\n9\nCena 12 B'
        self.fail_tick = False
    def read_currency(self, page):
        return getattr(self, 'currency', 'EUR')
    def read_page(self, page):
        return [SourceLine('b', i, text) for i, text in enumerate(self.text.split('\n'))]
    def mark_imported(self, expenses):
        if self.fail_tick:
            raise RuntimeError('Notion unavailable')
        lines = self.text.split('\n')
        for e in expenses:
            if not lines[e.line_index].endswith('✅'):
                lines[e.line_index] += ' ✅'
        self.text = '\n'.join(lines)


class Store:
    def __init__(self):
        self.records = {}
        self.writes = 0
    def load_imports(self):
        return self.records.copy()
    def commit_imports(self, items):
        self.writes += 1
        for item in items:
            assert item['id'] not in self.records
            self.records[item['id']] = item


def classifier(expenses):
    return {e.source_id: '🍔 Cibo fuori' for e in expenses}


def test_commit_then_tick_failure_retry_does_not_duplicate_and_month_is_pinned(tmp_path):
    notion, store = Notion(), Store()
    with Journal(tmp_path / 'sync.db') as journal:
        notion.fail_tick = True
        with pytest.raises(RuntimeError):
            sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), classifier=classifier)
        assert store.writes == 1
        assert next(iter(store.records.values()))['personal_eur'] == '6.00'
        notion.fail_tick = False
        sync_page('p', notion, journal, lambda year: store, date(2026, 12, 1), classifier=lambda e: pytest.fail('must not classify twice'))
        assert store.writes == 1
        assert notion.text.endswith('✅')
        assert next(iter(store.records.values()))['date'] == '2026-11-09'


def test_delete_imported_then_add_new_expense_and_currency(tmp_path):
    notion, store = Notion(), Store()
    with Journal(tmp_path / 'sync.db') as journal:
        sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), classifier=classifier)
        notion.text = 'Valuta: EUR'
        sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), classifier=classifier)
        notion.text = 'Valuta: EUR\n10\nCaffe 2'
        sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), classifier=classifier)
        assert store.writes == 2
        assert len(store.records) == 2
        notion.text = 'Valuta: EUR'
        assert sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), classifier=classifier) == []


def test_dry_run_has_no_external_writes_and_no_state_file(tmp_path):
    notion, store = Notion(), Store()
    path = tmp_path / 'sync.db'
    with Journal(path, dry_run=True) as journal:
        preview = sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), dry_run=True, classifier=classifier)
    assert preview[0]['bea_eur'] == '6.00'
    assert store.writes == 0
    assert not notion.text.endswith('✅')
    assert not path.exists()


def test_checked_lines_are_not_imported(tmp_path):
    notion, store = Notion(), Store()
    notion.text += ' ✅'
    with Journal(tmp_path / 'sync.db') as journal:
        assert sync_page('p', notion, journal, lambda year: store, date(2026, 11, 10), classifier=lambda e: pytest.fail()) == []
    assert store.writes == 0


def test_lost_journal_fails_closed_instead_of_duplicating(tmp_path):
    notion, store = Notion(), Store()
    notion.fail_tick = True
    with Journal(tmp_path / 'original.db') as journal:
        with pytest.raises(RuntimeError):
            sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=classifier)
    with Journal(tmp_path / 'lost.db') as journal:
        with pytest.raises(ValueError, match='journal'):
            sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=classifier)
    assert store.writes == 1


@pytest.mark.parametrize('edited', ['Cena 99 B ✅', 'Cena 99 B'])
def test_edit_imported_expense_does_not_block_unchecked_expenses(tmp_path, edited):
    notion, store = Notion(), Store()
    with Journal(tmp_path / 'sync.db') as journal:
        sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=classifier)
        notion.text = f'Valuta: EUR\n9\n{edited}\nCaffe 2'
        preview = sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=classifier)
        assert [r['description'] for r in preview] == (['Caffe'] if edited.endswith('✅') else ['Cena', 'Caffe'])
        assert all(line.endswith('✅') for line in notion.text.split('\n')[2:])
        assert next(iter(store.records.values()))['amount'] == '12'
        assert sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=lambda e: pytest.fail()) == []
    assert store.writes == 2


def test_removed_tick_is_restored_without_duplicate_import(tmp_path):
    notion, store = Notion(), Store()
    with Journal(tmp_path / 'sync.db') as journal:
        sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=classifier)
        notion.text = 'Valuta: EUR\n9\nCena 12 B'
        assert sync_page('p', notion, journal, lambda y: store, date(2026, 11, 10), classifier=lambda e: pytest.fail()) == []
        assert notion.text.endswith('✅')
    assert store.writes == 1


def test_lost_journal_checks_previous_year_before_new_year_import(tmp_path):
    from colf.notion_sync.run import check_continuity
    old, current = Store(), Store()
    old.records['previous-year-import'] = {'id': 'previous-year-import', 'date': '2026-12-09'}
    with Journal(tmp_path / 'lost.db') as journal:
        with pytest.raises(ValueError, match='journal'):
            check_continuity(journal, [old, current])
    assert current.writes == 0


def test_worker_uses_currency_select_without_text_header(tmp_path):
    notion, store = Notion(), Store()
    notion.text = '9\nCena 130 B'
    notion.currency = 'THB'
    def rate(currency, day):
        assert currency == 'THB'
        return Rate('THB', day, day, Decimal('0.027'))
    with Journal(tmp_path / 'sync.db') as journal:
        sync_page('p', notion, journal, lambda y: store, date(2026,11,10), classifier=classifier, rate_getter=rate)
    record = next(iter(store.records.values()))
    assert record['personal_eur'] == '1.75'
    assert record['bea_eur'] == '1.75'
