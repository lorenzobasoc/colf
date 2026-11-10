from datetime import date
from decimal import Decimal
import json
from types import SimpleNamespace
import pytest
from colf.notion_sync.model import SourceLine, parse_page
from colf.notion_sync.notion import Notion
from colf.notion_sync.conversion import get_rate, split_eur
from colf.notion_sync.claude import classify


def block(text, identifier='b'):
    return {'id': identifier, 'type': 'paragraph', 'has_children': False,
            'paragraph': {'rich_text': [{'type': 'text', 'text': {'content': text}, 'plain_text': text, 'annotations': {'bold': True}}]}}


def test_read_pagination_and_tick_preserves_other_lines_and_style():
    original = block('Valuta: THB\n9\nCena 130 B\n711 90')
    calls = []
    def request(method, path, payload=None):
        calls.append((method, path, payload))
        if 'children' in path:
            return {'results': [original], 'has_more': False}
        if method == 'GET':
            return original
        return {}
    client = Notion(request)
    expenses = parse_page('p', client.read_page('p'), today=date(2026, 11, 10))
    client.mark_imported(expenses[:1])
    rich = calls[-1][2]['paragraph']['rich_text']
    assert ''.join(r['text']['content'] for r in rich) == 'Valuta: THB\n9\nCena 130 B ✅\n711 90'
    assert rich[0]['annotations']['bold'] is True
    assert calls[-1][0] == 'PATCH'


def test_notion_does_not_overwrite_concurrent_edit():
    old = block('Valuta: EUR\n9\ncena 12')
    new = block('Valuta: EUR\n9\ncena 99')
    def request(method, path, payload=None):
        assert method == 'GET'
        return {'results': [old], 'has_more': False} if 'children' in path else new
    client = Notion(request)
    expenses = parse_page('p', client.read_page('p'), today=date(2026, 11, 10))
    with pytest.raises(ValueError, match='modificat'):
        client.mark_imported(expenses)


def test_historical_rate_and_split():
    def request(method, path, payload=None):
        assert '2026-11-09' in path
        return {'base': 'THB', 'quote': 'EUR', 'date': '2026-11-06', 'rate': Decimal('0.027')}
    rate = get_rate('THB', date(2026, 11, 9), request=request)
    assert rate.effective_date == date(2026, 11, 6)
    assert split_eur(Decimal('130'), rate, True) == (Decimal('1.75'), Decimal('1.75'))
    assert split_eur(Decimal('130'), rate, False) == (Decimal('3.50'), Decimal('0'))


def test_eur_without_network_and_bad_rates():
    assert get_rate('EUR', date(2026, 11, 9)).eur_per_unit == 1
    for day, rate in [('2026-11-10', '0.027'), ('2026-10-01', '0.027'), ('2026-11-09', '-1')]:
        with pytest.raises(ValueError):
            get_rate('THB', date(2026, 11, 9), request=lambda *args: {'base':'THB','quote':'EUR','date':day,'rate':Decimal(rate)})


def test_claude_validates_output_and_uses_no_tools(monkeypatch):
    for name in list(__import__('os').environ):
        if name.startswith('ANTHROPIC_') or name.startswith('CLAUDE_CODE_USE_'):
            monkeypatch.delenv(name)
    expenses = parse_page('p', [SourceLine('b', 0, 'Valuta: EUR'), SourceLine('b', 1, '9'), SourceLine('b', 2, 'cena 12')], today=date(2026, 11, 9))
    def run(command, **kwargs):
        if 'auth' in command:
            return SimpleNamespace(returncode=0, stdout= '{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty"}')
        assert command[command.index('--model') + 1] == 'claude-haiku-5-5'
        assert command[command.index('--tools') + 1] == ''
        assert '--bare' not in command
        assert 'cena' in kwargs['input']
        return SimpleNamespace(returncode=0, stdout=json.dumps({'structured_output': {'categories': [{'id': expenses[0].source_id, 'category': 'Cibo fuori'}]}}))
    assert classify(expenses, runner=run)[expenses[0].source_id] == '🍔 Cibo fuori'
    with pytest.raises(ValueError):
        classify(expenses, runner=lambda *a, **kw: SimpleNamespace(returncode=0, stdout='{"structured_output":{"categories":[]}}'))


def test_claude_rejects_api_billing(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-no-real-key')
    with pytest.raises(ValueError, match='API'):
        classify([object()])


def test_claude_refuses_non_subscription_auth(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(ValueError, match='abbonamento'):
        classify([object()], runner=lambda *a, **kw: SimpleNamespace(returncode=0, stdout='{"loggedIn":true,"authMethod":"api_key"}'))


def test_tick_rejects_changed_day_header_even_when_expense_unchanged():
    old = block('Valuta: EUR\n9\ncena 12')
    new = block('Valuta: EUR\n10\ncena 12')
    def request(method, path, payload=None):
        assert method == 'GET'
        return {'results': [old], 'has_more': False} if 'children' in path else new
    client = Notion(request)
    expenses = parse_page('p', client.read_page('p'), today=date(2026, 11, 10))
    with pytest.raises(ValueError, match='modificat'):
        client.mark_imported(expenses)


def test_notion_pagination_keeps_block_order():
    def request(method, path, payload=None):
        if 'start_cursor=next' in path:
            return {'results':[block('cena 12','c')], 'has_more':False}
        return {'results':[block('Valuta: EUR\n9','a')], 'has_more':True, 'next_cursor':'next'}
    client = Notion(request)
    result = parse_page('p', client.read_page('p'), today=date(2026,11,10))
    assert result[0].description == 'cena'
    assert result[0].block_id == 'c'


def test_currency_is_read_from_notion_select_property():
    def request(method, path, payload=None):
        assert (method, path) == ('GET', '/pages/p')
        return {'properties': {'Valuta': {'type': 'select', 'select': {'name': 'THB'}}}}
    assert Notion(request).read_currency('p') == 'THB'


@pytest.mark.parametrize('properties', [{}, {'Valuta': {'type': 'select', 'select': None}}, {'Valuta': {'type': 'rich_text', 'rich_text': []}}])
def test_currency_select_required(properties):
    with pytest.raises(ValueError, match='Valuta'):
        Notion(lambda *args: {'properties': properties}).read_currency('p')


@pytest.mark.parametrize(('amount','expected'), [('1.73','1.75'),('1.46','1.45'),('1.20','1.20'),('1.33','1.35'),('1.24','1.25'),('1.25','1.25'),('1.75','1.75'),('0.0249','0.00'),('0.025','0.05')])
def test_rounds_eur_to_nearest_five_cents_without_double_rounding(amount, expected):
    rate = get_rate('EUR', date(2026,11,10))
    assert split_eur(Decimal(amount), rate, False) == (Decimal(expected), Decimal('0'))


def test_shared_expense_rounds_each_half_after_conversion():
    from colf.notion_sync.conversion import Rate
    rate = Rate('THB',date(2026,11,9),date(2026,11,9),Decimal('0.026677'))
    assert split_eur(Decimal('130'),rate,True) == (Decimal('1.75'),Decimal('1.75'))
