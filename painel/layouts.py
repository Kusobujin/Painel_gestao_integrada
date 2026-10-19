"""Definições de layouts, independentes dos dados operacionais."""
from copy import deepcopy
from uuid import uuid4

from .charts import ChartPanel

SETTINGS_KEY = 'custom_layouts_v1'
SIZES = {'Normal': (1, 1), 'Largo': (2, 1), 'Alto': (1, 2), 'Tela inteira': (2, 2)}
INTERVALS = (5, 10, 15, 30, 60)


def new_layout(name='Meu layout'):
    return {'id': uuid4().hex, 'name': name, 'enabled': True, 'seconds': 10, 'items': []}


def new_item(kind, areas):
    keys = [a.key for a in areas]
    return {'id': uuid4().hex, 'kind': kind, 'x': 0, 'y': 0, 'w': 1, 'h': 1,
            'metric': 'Atingimento (%)' if kind == 'chart' else 'Resumo do setor',
            'chart': 'Barras horizontais', 'areas': keys[:8] if kind == 'chart' else keys[:1]}


def cells(item):
    return {(x, y) for x in range(item['x'], item['x']+item['w'])
            for y in range(item['y'], item['y']+item['h'])}


def fits(layout, item, exclude=()):
    if item['x'] < 0 or item['y'] < 0 or item['x']+item['w'] > 2 or item['y']+item['h'] > 2:
        return False
    return all(not (cells(item) & cells(other)) for other in layout['items']
               if other['id'] != item['id'] and other['id'] not in exclude)


def add_item(layout, item, position=None):
    for x, y in ([position] if position is not None else [(0, 0), (1, 0), (0, 1), (1, 1)]):
        candidate = {**item, 'x': x, 'y': y}
        if fits(layout, candidate):
            layout['items'].append(candidate)
            return candidate
    return None


def move_item(layout, item_id, x, y):
    item = next(i for i in layout['items'] if i['id'] == item_id)
    candidate = {**item, 'x': x, 'y': y}
    if fits(layout, candidate):
        item.update(candidate)
        return True
    others = [i for i in layout['items'] if i['id'] != item_id and cells(i) & cells(candidate)]
    if len(others) == 1 and (others[0]['w'], others[0]['h']) == (item['w'], item['h']):
        other = others[0]
        swapped = {**other, 'x': item['x'], 'y': item['y']}
        if fits(layout, candidate, [other['id']]) and fits(layout, swapped, [item['id']]):
            item.update(candidate)
            other.update(swapped)
            return True
    return False


def resize_item(layout, item_id, size):
    item = next(i for i in layout['items'] if i['id'] == item_id)
    w, h = SIZES[size]
    for x, y in [(min(item['x'], 2-w), min(item['y'], 2-h)), (0, 0), (1, 0), (0, 1), (1, 1)]:
        candidate = {**item, 'x': x, 'y': y, 'w': w, 'h': h}
        if fits(layout, candidate):
            item.update(candidate)
            return True
    return False


def duplicate_layout(layout):
    result = deepcopy(layout)
    result['id'], result['name'] = uuid4().hex, layout['name']+' (cópia)'
    for item in result['items']:
        item['id'] = uuid4().hex
    return result


def validate_layouts(layouts):
    ids = set()
    for layout in layouts:
        if not layout.get('name', '').strip():
            raise ValueError('Dê um nome a cada layout.')
        if layout['id'] in ids:
            raise ValueError('Há layouts com identificação repetida.')
        ids.add(layout['id'])
        if layout['seconds'] not in INTERVALS:
            raise ValueError('Escolha um tempo de apresentação válido.')
        if not layout['items']:
            raise ValueError(f'Adicione um bloco em “{layout["name"]}” antes de salvar.')
        item_ids = set()
        for item in layout['items']:
            if item['id'] in item_ids:
                raise ValueError('Há blocos repetidos no layout.')
            item_ids.add(item['id'])
            if (item['w'], item['h']) not in SIZES.values() or not fits(layout, item):
                raise ValueError('Os blocos precisam caber na tela, sem sobreposição.')
            if item['kind'] not in ('chart', 'indicator') or not item['areas']:
                raise ValueError('Escolha um setor para cada bloco.')
            if item['kind'] == 'chart':
                if item['metric'] not in ChartPanel.METRICS or item['chart'] not in ChartPanel.TYPES:
                    raise ValueError('Escolha indicador e formato válidos para o gráfico.')
                if item['chart'] == 'Distribuição de status' and item['metric'] != 'Atingimento (%)':
                    raise ValueError('Distribuição de status usa Atingimento (%).')
                if ChartPanel.METRICS[item['metric']] not in ('percentual', 'falta') and len(item['areas']) != 1:
                    raise ValueError('Valores absolutos precisam de um único setor por gráfico.')
            elif item['metric'] not in ('Resumo do setor', *ChartPanel.METRICS):
                raise ValueError('Escolha um indicador válido para o cartão.')
            elif len(item['areas']) != 1:
                raise ValueError('Cada cartão de indicador apresenta um setor.')


class LayoutStore:
    def __init__(self, repo):
        self.repo = repo

    def load(self):
        saved = self.repo.get_setting(SETTINGS_KEY, {'version': 1, 'layouts': []})
        return deepcopy(saved.get('layouts', []))

    def save(self, layouts):
        validate_layouts(layouts)
        self.repo.set_setting(SETTINGS_KEY, {'version': 1, 'layouts': deepcopy(layouts)})
