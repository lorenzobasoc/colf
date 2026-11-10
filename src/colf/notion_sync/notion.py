from collections import defaultdict
from copy import deepcopy
from urllib.parse import urlencode

from .http import json_client
from .model import SourceLine, SourceExpense

_TEXT_TYPES = {'paragraph', 'bulleted_list_item', 'numbered_list_item',
               'heading_1', 'heading_2', 'heading_3'}


def text_of(block):
    kind = block['type']
    if kind not in _TEXT_TYPES:
        if kind == 'divider':
            return ''
        raise ValueError(f'Tipo blocco Notion non supportato: {kind}')
    rich = block[kind].get('rich_text', [])
    if any(item.get('type', 'text') != 'text' for item in rich):
        raise ValueError('Usare testo semplice per le spese, senza mention o formule')
    return ''.join(item['text']['content'] for item in rich)


class Notion:
    def __init__(self, request):
        self.request = request
        self.snapshots = {}

    @classmethod
    def from_token(cls, token: str):
        return cls(json_client('https://api.notion.com/v1', {
            'Authorization': f'Bearer {token}', 'Notion-Version': '2025-09-03'}))

    def read_currency(self, page_id: str) -> str:
        page = self.request('GET', f'/pages/{page_id}')
        prop = page.get('properties', {}).get('Valuta', {})
        value = prop.get('select') if prop.get('type') == 'select' else None
        if not value or not isinstance(value.get('name'), str) or not value['name'].strip():
            raise ValueError('Impostare la proprietà Select Valuta sulla pagina Notion (es. THB o EUR)')
        return value['name'].strip().upper()

    def read_page(self, page_id: str) -> list[SourceLine]:
        lines = []
        cursor = None
        while True:
            query = urlencode({'page_size': 100, **({'start_cursor': cursor} if cursor else {})})
            response = self.request('GET', f'/blocks/{page_id}/children?{query}')
            for block in response['results']:
                self.snapshots[block['id']] = text_of(block)
                lines.extend(SourceLine(block['id'], i, line)
                             for i, line in enumerate(text_of(block).split('\n')))
                if block.get('has_children'):
                    lines.extend(self.read_page(block['id']))
            if not response.get('has_more'):
                return lines
            cursor = response['next_cursor']

    def mark_imported(self, expenses: list[SourceExpense]) -> None:
        grouped = defaultdict(list)
        for expense in expenses:
            grouped[expense.block_id].append(expense)
        for block_id, group in grouped.items():
            block = self.request('GET', f'/blocks/{block_id}')
            original = text_of(block)
            expected = self.snapshots.get(block_id)
            normalize = lambda text: [line.rstrip().removesuffix('✅').rstrip() for line in text.split('\n')]
            if expected is None or normalize(original) != normalize(expected):
                raise ValueError(f'Blocco Notion modificato: {block_id}; tick da riconciliare')
            lines = original.split('\n')
            offsets = []
            for expense in group:
                i = expense.line_index
                if i >= len(lines) or lines[i].strip().removesuffix('✅').strip() != expense.text.strip().removesuffix('✅').strip():
                    raise ValueError(f'Blocco Notion modificato: {block_id}; tick da riconciliare')
                if not lines[i].strip().endswith('✅'):
                    offsets.append(sum(len(line) + 1 for line in lines[:i]) + len(lines[i].rstrip()))
            if not offsets:
                continue
            # Insert suffixes into rich-text spans without flattening formatting or links.
            rich = []
            start = 0
            for item in block[block['type']]['rich_text']:
                span = deepcopy({key: value for key, value in item.items()
                                 if key in {'type', 'text', 'annotations'}})
                content = span['text']['content']
                end = start + len(content)
                for offset in sorted((x for x in offsets if start < x <= end), reverse=True):
                    relative = offset - start
                    content = content[:relative] + ' ✅' + content[relative:]
                span['text']['content'] = content
                if len(content) > 2000:
                    # Preserve each span's attributes while respecting Notion's content limit.
                    for i in range(0, len(content), 2000):
                        part = deepcopy(span)
                        part['text']['content'] = content[i:i + 2000]
                        rich.append(part)
                else:
                    rich.append(span)
                start = end
            if len(rich) > 100:
                raise ValueError('Blocco troppo grande per aggiornamento Notion')
            self.request('PATCH', f'/blocks/{block_id}', {block['type']: {'rich_text': rich}})
