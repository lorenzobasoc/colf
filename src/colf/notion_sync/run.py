"""Run with: python -m colf.notion_sync.run [--dry-run]."""
import argparse
from collections import defaultdict
from contextlib import AbstractContextManager
from datetime import date, datetime
import fcntl
import json
import logging
import os
from pathlib import Path
import sqlite3
import uuid
from zoneinfo import ZoneInfo

from .claude import classify
from .conversion import get_rate, split_eur
from .model import parse_page
from .notion import Notion
from .sheets import SheetStore

logger = logging.getLogger(__name__)


class Journal(AbstractContextManager):
    """Persist first observation/date and prepared values before any remote writes."""
    def __init__(self, path, *, dry_run=False):
        path = Path(path)
        if dry_run:
            self.db = sqlite3.connect(':memory:')
            if path.exists():
                with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True) as source:
                    source.backup(self.db)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path)
            os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS observed (
            id TEXT PRIMARY KEY, page TEXT NOT NULL, source TEXT NOT NULL,
            date TEXT NOT NULL, ignored INTEGER NOT NULL, active INTEGER NOT NULL,
            prepared TEXT, block TEXT NOT NULL, marked INTEGER NOT NULL)''')
        self.db.commit()

    def __exit__(self, *args):
        self.db.close()

    def bind(self, page, expenses, today):
        active = {row['source']: dict(row) for row in self.db.execute(
            'SELECT * FROM observed WHERE page=? AND active=1', (page,))}
        result = []
        current_keys = {e.source_id for e in expenses}
        removed_blocks = {entry['block'] for key, entry in active.items()
                          if key not in current_keys and entry['prepared']}
        for expense in expenses:
            if expense.source_id not in active and expense.block_id in removed_blocks:
                raise ValueError('Spesa importata modificata: usare un nuovo blocco Notion per nuove spese')
            if expense.source_id in active and active[expense.source_id]['marked'] and not expense.checked:
                raise ValueError('tick rimosso o acquisto identico nello stesso blocco: riconciliazione richiesta')
        with self.db:
            self.db.execute('UPDATE observed SET active=0 WHERE page=?', (page,))
            for expense in expenses:
                entry = active.get(expense.source_id)
                if entry is None:
                    day = today if expense.checked else expense.expense_date(today)
                    entry = {'id': uuid.uuid4().hex, 'page': page, 'source': expense.source_id,
                             'date': day.isoformat(), 'ignored': int(expense.checked), 'active': 1,
                             'prepared': None, 'block': expense.block_id, 'marked': int(expense.checked)}
                    self.db.execute('INSERT INTO observed VALUES (:id,:page,:source,:date,:ignored,:active,:prepared,:block,:marked)', entry)
                else:
                    self.db.execute('UPDATE observed SET active=1 WHERE id=?', (entry['id'],))
                result.append((expense, entry))
        return result

    def ids(self):
        return {row[0] for row in self.db.execute('SELECT id FROM observed')}

    def mark(self, identifiers):
        with self.db:
            self.db.executemany('UPDATE observed SET marked=1 WHERE id=?', [(i,) for i in identifiers])

    def prepared(self, identifier, record):
        with self.db:
            self.db.execute('UPDATE observed SET prepared=? WHERE id=?',
                            (json.dumps(record, ensure_ascii=False), identifier))


def check_continuity(journal, stores):
    known_ids = journal.ids()
    for store in stores:
        if set(store.load_imports()) - known_ids:
            raise ValueError('Continuità journal persa: ripristinare il database locale dal backup')


def sync_page(page_id, notion, journal, store_for_year, today, *, dry_run=False,
              classifier=classify, rate_getter=get_rate):
    currency = notion.read_currency(page_id)
    expenses = parse_page(page_id, notion.read_page(page_id), today=today, currency=currency)
    bound = journal.bind(page_id, expenses, today)
    stores, known = {}, {}
    pending, tick = [], []
    for expense, entry in bound:
        if entry['ignored']:
            continue
        year = date.fromisoformat(entry['date']).year
        if year not in stores:
            stores[year] = store_for_year(year)
            known[year] = stores[year].load_imports()
            if set(known[year]) - journal.ids():
                raise ValueError('Continuità journal persa: ripristinare il database locale dal backup')
        if entry['id'] in known[year]:
            if entry['prepared'] and known[year][entry['id']] != json.loads(entry['prepared']):
                raise ValueError('Registro Google e journal locale discordanti')
            if not expense.checked:
                tick.append(expense)
        elif expense.checked:
            # Manual ticks are accepted as already dealt with; never import them.
            continue
        else:
            pending.append((expense, entry))
    fresh = [expense for expense, entry in pending if not entry['prepared']]
    categories = classifier(fresh) if fresh else {}
    rates = {}
    prepared = []
    for expense, entry in pending:
        if entry['prepared']:
            record = json.loads(entry['prepared'])
        else:
            day = date.fromisoformat(entry['date'])
            key = expense.currency, day
            if key not in rates:
                rates[key] = rate_getter(*key)
            rate = rates[key]
            personal, bea = split_eur(expense.amount, rate, expense.shared)
            record = {'id': entry['id'], 'page': page_id, 'source': expense.source_id,
                'date': day.isoformat(), 'description': expense.description,
                'amount': str(expense.amount), 'currency': expense.currency,
                'shared': expense.shared, 'category': categories[expense.source_id],
                'personal_eur': f'{personal:.2f}', 'bea_eur': f'{bea:.2f}',
                'rate': str(rate.eur_per_unit), 'rate_date': rate.effective_date.isoformat()}
            journal.prepared(entry['id'], record)
        prepared.append(record)
        tick.append(expense)
    if dry_run:
        return prepared
    groups = defaultdict(list)
    for record in prepared:
        groups[date.fromisoformat(record['date']).year].append(record)
    for year, records in groups.items():
        stores[year].commit_imports(records)
    # A failed tick is recovered from the Google ledger on the next run.
    notion.mark_imported(tick)
    journal.mark(entry['id'] for expense, entry in bound if expense in tick or expense.checked)
    logger.info('Pagina %s: %d spese importate; %d tick da confermare', page_id, len(prepared), len(tick))
    return prepared


def main():
    parser = argparse.ArgumentParser(description='Importa spese testuali Notion in Google Sheets')
    parser.add_argument('--dry-run', action='store_true', help='Anteprima senza scritture Google/Notion o journal persistente')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    from dotenv import load_dotenv
    load_dotenv()
    state_path = Path(os.environ.get('SYNC_STATE_PATH', 'data/notion-sync.db')).expanduser()
    lock_path = Path(os.environ.get('SYNC_LOCK_PATH', str(state_path) + '.lock')).expanduser()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                logger.info('Importazione già in corso; controllo saltato')
                return 0
            # Keep imports and config separate from the existing invoices/local-LLM app.
            import gspread
            spreadsheets = json.loads(os.environ['SYNC_SPREADSHEETS'])
            if not isinstance(spreadsheets, dict) or not spreadsheets:
                raise ValueError('SYNC_SPREADSHEETS deve associare anno a spreadsheet ID')
            client = gspread.service_account(filename=os.environ['GOOGLE_SERVICE_ACCOUNT_PATH'])
            stores = {}
            def store_for_year(year):
                if str(year) not in spreadsheets:
                    raise ValueError(f'Spreadsheet non configurato per anno {year}')
                if year not in stores:
                    spreadsheet = client.open_by_key(spreadsheets[str(year)])
                    # Read-only requests may retry throttling; mutations must never retry implicitly.
                    stores[year] = SheetStore(spreadsheet)
                return stores[year]
            notion = Notion.from_token(os.environ['NOTION_TOKEN'])
            pages = [p.strip() for p in os.environ['NOTION_PAGE_IDS'].split(',') if p.strip()]
            if not pages:
                raise ValueError('NOTION_PAGE_IDS vuoto')
            today = datetime.now(ZoneInfo(os.environ.get('SYNC_TIMEZONE', 'Europe/Rome'))).date()
            binary = os.environ.get('CLAUDE_BIN', 'claude')
            with Journal(state_path, dry_run=args.dry_run) as journal:
                # Check every configured year before binding current-month rows.
                # Otherwise a lost journal at New Year could duplicate December into January.
                check_continuity(journal, (store_for_year(int(year)) for year in spreadsheets))
                for page in pages:
                    preview = sync_page(page, notion, journal, store_for_year, today,
                        dry_run=args.dry_run, classifier=lambda expenses: classify(expenses, binary=binary))
                    if args.dry_run:
                        print(json.dumps(preview, ensure_ascii=False, indent=2))
    except Exception as error:
        # Never log tokens or raw HTTP response bodies / Claude prompts.
        logger.error('Importazione sospesa (%s): %s', type(error).__name__, error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
