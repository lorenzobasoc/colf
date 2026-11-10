from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
import re


@dataclass(frozen=True)
class SourceLine:
    block_id: str
    line_index: int
    text: str


@dataclass(frozen=True)
class SourceExpense:
    source_id: str
    block_id: str
    line_index: int
    text: str
    day: int
    description: str
    amount: Decimal
    currency: str
    shared: bool
    checked: bool

    def expense_date(self, today: date) -> date:
        value = date(today.year, today.month, self.day)
        if value > today:
            raise ValueError(f'Giorno futuro o arretrato ambiguo: {self.day}')
        return value


def parse_page(page_id: str, lines: list[SourceLine], *, today: date, currency: str | None = None) -> list[SourceExpense]:
    seen_header = False
    for line in lines:
        if line.text.strip().lower().startswith('valuta:'):
            if seen_header:
                raise ValueError('Una sola intestazione Valuta per pagina')
            seen_header = True
            header = line.text.split(':', 1)[1].strip().upper()
            if currency is not None and header != currency:
                raise ValueError('Valuta nel testo diversa dalla proprietà Valuta della pagina')
            currency = header
    if not currency or not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('Intestazione richiesta: Valuta: THB (o altro codice ISO)')
    day = None
    result = []
    counts = Counter()
    for line in lines:
        text = line.text.strip()
        if not text or text.lower().startswith('valuta:'):
            continue
        if re.fullmatch(r'\d{1,2}', text):
            day = int(text)
            if not 1 <= day <= 31:
                raise ValueError(f'Giorno non valido: {day}')
            continue
        checked = text.endswith('✅')
        raw = text.removesuffix('✅').strip()
        match = re.fullmatch(r'(.+?)\s+(\d+(?:[.,]\d+)?)\s*(B)?', raw, re.IGNORECASE)
        if day is None or not match:
            raise ValueError(f'Riga spesa non valida: blocco {line.block_id}, riga {line.line_index + 1}')
        description, amount, shared = match.groups()
        amount = Decimal(amount.replace(',', '.'))
        if amount <= 0:
            raise ValueError('Importo deve essere positivo')
        # Content identity survives deletion of unrelated lines in a multiline block.
        key = (page_id, line.block_id, day, description.strip(), str(amount), bool(shared))
        occurrence = counts[key]
        counts[key] += 1
        source_id = hashlib.sha256(json.dumps([*key, occurrence]).encode()).hexdigest()
        result.append(SourceExpense(source_id, line.block_id, line.line_index,
                                    line.text, day, description.strip(), amount,
                                    currency, bool(shared), checked))
    return result
