from datetime import date
from decimal import Decimal
import pytest
from colf.notion_sync.model import SourceLine, parse_page


def lines(text):
    return [SourceLine('block', i, line) for i, line in enumerate(text.splitlines())]


def test_text_currency_shared_numeric_merchant_and_tick():
    result = parse_page('page', lines('Valuta: THB\n\n9\nCena 130 B\n711 130 B ✅\n\n10\nCaffe 110 B'), today=date(2026, 11, 10))
    assert [(e.day, e.description, e.amount, e.shared, e.checked) for e in result] == [
        (9, 'Cena', Decimal('130'), True, False),
        (9, '711', Decimal('130'), True, True),
        (10, 'Caffe', Decimal('110'), True, False)]
    assert result[0].currency == 'THB'


def test_deleting_other_lines_does_not_change_identity():
    before = parse_page('page', lines('Valuta: EUR\n12\ncena 12 ✅\nlupo 1'), today=date(2026, 11, 12))
    after = parse_page('page', lines('Valuta: EUR\n12\nlupo 1'), today=date(2026, 11, 12))
    assert before[1].source_id == after[0].source_id


def test_duplicate_purchases_have_distinct_ids():
    result = parse_page('p', lines('Valuta: EUR\n12\ncena 12\ncena 12'), today=date(2026, 11, 12))
    assert len({e.source_id for e in result}) == 2


@pytest.mark.parametrize('text', ['12\ncena 2', 'Valuta: THB\n32\ncena 2', 'Valuta: EUR\n12\ncena NaN', 'Valuta: EUR\n12\ncena -2', 'Valuta: EUR\ncena 2'])
def test_rejects_invalid_input(text):
    with pytest.raises(ValueError):
        parse_page('p', lines(text), today=date(2026, 11, 12))


def test_currency_from_page_property_without_body_header():
    result = parse_page('p', lines('9\nCena 130 B'), today=date(2026, 11, 10), currency='THB')
    assert result[0].currency == 'THB'
    assert result[0].description == 'Cena'


def test_body_header_cannot_override_currency_property():
    with pytest.raises(ValueError, match='valuta|Valuta'):
        parse_page('p', lines('Valuta: EUR\n9\nCena 130'), today=date(2026, 11, 10), currency='THB')
