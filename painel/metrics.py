"""Cálculo de indicadores e apresentação de unidades."""
import calendar
from datetime import date, timedelta
from typing import Optional
from .config import AREAS, destination_channel, THRESHOLD_ATTENTION, THRESHOLD_CRITICAL


def number(value):
    """Converte campos numéricos de fontes externas com segurança."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        import math
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        txt = value.strip().replace('R$', '').replace(' ', '')
        if not txt or txt.startswith('#') or txt in ('—', '-'):
            return None
        if ',' in txt and '.' in txt:
            txt = txt.replace('.', '').replace(',', '.')
        elif ',' in txt:
            txt = txt.replace(',', '.')
        try:
            result = float(txt)
            return result if __import__('math').isfinite(result) else None
        except ValueError:
            return None
    return None


def fmt_number(v: Optional[float]):
    if v is None:
        return '—'
    if abs(v) >= 1000:
        decimals = 0 if v.is_integer() else 1
    elif abs(v) >= 10:
        decimals = 0 if v.is_integer() else 2
    elif abs(v) >= 1:
        decimals = 0 if v.is_integer() else 2
    else:
        decimals = 3 if abs(v) < 1 else 2
    s = f'{v:,.{decimals}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def fmt_cell(v, metric: str, area_key: str):
    if v is None:
        return '—'
    if metric in ('percentual', 'falta') or (area_key == 'garantia' and metric in ('capacidade', 'stk_pai')):
        return (f'{v * 100:.1f}%').replace('.', ',')
    return fmt_number(v)


def status_of(attainment):
    if attainment is None:
        return 'sem_dados'
    if attainment < THRESHOLD_CRITICAL:
        return 'critico'
    if attainment < THRESHOLD_ATTENTION:
        return 'atencao'
    return 'no_alvo'


def get_value(snapshot, area_key, metric, area=None):
    area = area or next((a for a in AREAS if a.key == area_key), None)
    if area is None:
        return None
    channel = destination_channel(area, metric)
    return snapshot.areas.get(area_key, {}).get(metric, {}).get(channel)


def set_value(snapshot, area_key, metric, channel, new_value, area=None):
    snapshot.areas.setdefault(area_key, {}).setdefault(metric, {})[channel] = new_value
    # Atingimento/Gap são recalculados quando o usuário muda os dois componentes.
    area = area or next((a for a in AREAS if a.key == area_key), None)
    if area is None:
        return
    ch = destination_channel(area, 'mes')
    actual = snapshot.areas[area_key].get('mes', {}).get(ch)
    goal = snapshot.areas[area_key].get('fcst', {}).get(ch)
    if metric in ('mes', 'fcst') and actual is not None and goal not in (None, 0):
        attainment = actual / goal
        snapshot.areas[area_key].setdefault('percentual', {})[ch] = attainment
        snapshot.areas[area_key].setdefault('falta', {})[ch] = max(0.0, 1 - attainment)
        snapshot.errors.setdefault(area_key, {}).pop('percentual', None)
    elif metric == 'percentual':
        if new_value is not None:
            snapshot.areas[area_key].setdefault('falta', {})[channel] = max(0.0, 1 - new_value)
    snapshot.errors.setdefault(area_key, {}).pop(metric, None)


def summary(snapshot, area_keys, areas=None):
    lookup = {a.key: a for a in (areas or AREAS)}
    values = [get_value(snapshot, k, 'percentual', lookup.get(k)) for k in area_keys]
    known = [v for v in values if v is not None]
    return {
        'areas': len(area_keys),
        'known': len(known),
        'good': sum(v >= THRESHOLD_ATTENTION for v in known),
        'attention': sum(v < THRESHOLD_ATTENTION for v in known),
        'warning': sum(THRESHOLD_CRITICAL <= v < THRESHOLD_ATTENTION for v in known),
        'critical': sum(v < THRESHOLD_CRITICAL for v in known),
        'missing': len(values) - len(known),
        'gap_average': sum(max(0., 1 - v) for v in known) / len(known) if known else None,
    }


def follow_up_areas(snapshot, areas):
    """Menores atingimentos conhecidos e pendências, sem misturar unidades."""
    below, missing = [], []
    for area in areas:
        value = get_value(snapshot, area.key, 'percentual', area) if snapshot else None
        if value is None:
            missing.append(area)
        elif value < THRESHOLD_ATTENTION:
            below.append((area, value))
    return sorted(below, key=lambda pair: pair[1]), missing


def business_days(reference: date, today: Optional[date] = None):
    """Segunda a sexta. Sem calendário de feriados — exibido na UI."""
    today = today or date.today()
    last = calendar.monthrange(reference.year, reference.month)[1]
    dates = [date(reference.year, reference.month, d) for d in range(1, last + 1)]
    total = sum(d.weekday() < 5 for d in dates)
    remaining = sum(d.weekday() < 5 and d > today for d in dates)
    return total, remaining
