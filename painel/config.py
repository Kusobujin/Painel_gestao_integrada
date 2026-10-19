"""Configurações, paleta e esquema da planilha GERENCIAL."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    key: str
    title: str
    short: str
    primary: str
    secondary: str
    excel_col: str


AREAS = (
    Area('linc', 'LINC', 'LINC', 'Entrada Pedido (Qtd)', '', 'D'),
    Area('logistica', 'LOGÍSTICA', 'LOGÍSTICA', 'Pedidos a Faturar (R$)', 'Pedidos Faturados ($)', 'F'),
    Area('transporte', 'TRANSPORTE', 'TRANSPORTE', 'Entregas Trânsito (R$)', 'Entregas Realizadas', 'H'),
    Area('recebimento', 'RECEBIMENTO', 'RECEBIMENTO', 'Material a Receber (Qtd Pçs)', 'Total Recebido', 'J'),
    Area('embalagem', 'EMBALAGEM', 'EMBALAGEM', 'Material a Embalar (Qtde)', 'TT Rec / Embal', 'L'),
    Area('sensor', 'MANUFATURA (SENSOR OXIGÊNIO)', 'SENSOR OXIGÊNIO', 'Produção (Qtde)', 'Produzido', 'N'),
    Area('eui', 'MANUFATURA (EUI - VOLVO)', 'EUI - VOLVO', 'Produção (Qtde)', 'Produzido', 'P'),
    Area('reman_mbb', 'MANUFATURA (FALSO REMAN MBB)', 'FALSO REMAN MBB', 'Produção (Qtde)', 'Produzido', 'R'),
    Area('cr_iam', 'MANUFATURA (CR -IAM)', 'CR - IAM', 'Produção (Qtde)', 'Produzido', 'T'),
    Area('cabecote', 'CABEÇOTE REMAN', 'CABEÇOTE REMAN', 'Produção FS (Qtd)', 'Qtd Entregue', 'V'),
    Area('pessoas', 'PESSOAS', 'PESSOAS', 'Todas as Áreas (Qtd)', 'Média Pessoas', 'X'),
    Area('garantia', 'GARANTIA (SEMANAL W40)', 'GARANTIA W40', 'Vlr em R$ a Pagar (M)', 'Valor Já Pago 2026', 'Z'),
)
AREA_BY_KEY = {area.key: area for area in AREAS}

ROWS = (
    ('dia', 'DIA', 'Indicador diário'),
    ('capacidade', 'CAP. / SALDO', 'Capacidade ou saldo'),
    ('mes', 'MÊS', 'Realizado / acumulado'),
    ('stk_pai', 'STK PAI', 'Estoque pai'),
    ('stk_filho', 'STK FILHO', 'Estoque filho'),
    ('fcst', 'FCST / BBP', 'Meta / projeção mensal'),
    ('percentual', 'ATINGIMENTO %', 'Realizado ÷ meta'),
    ('falta', 'FALTA %', 'Gap até a meta'),
)
ROW_BY_KEY = {r[0]: r for r in ROWS}
ROW_GROUPS = {
    'Todos': tuple(r[0] for r in ROWS),
    'Diário': ('dia', 'capacidade'),
    'Mensal': ('mes',),
    'Estoques': ('stk_pai', 'stk_filho'),
    'Metas e desempenho': ('fcst', 'percentual', 'falta'),
}

# A planilha GERENCIAL possui uma coluna de valores por área.
# Os dois rótulos de cada área aparecem em linhas diferentes (linhas 4 e 8).
# O programa apresenta esses rótulos em duas subcolunas visuais, sem duplicar valores.
EXCEL_ROW_MAP = {
    'dia': 5,
    'capacidade': 6,
    'mes': 9,
    'stk_pai': 10,
    'fcst': 13,
    'stk_filho': 14,
    'percentual': 17,
}

# Identidade visual PGI: grafite/preto + vermelho industrial.
# Verde e âmbar permanecem APENAS em indicadores semânticos de desempenho.
C = {
    'bg': '#090A0D',
    'sidebar': '#111216',
    'surface': '#17191F',
    'surface_2': '#20232B',
    'surface_3': '#282C35',
    'stripe': '#1C1E25',
    'stroke': '#383C46',
    'text': '#F7F7F9',
    'muted': '#B0B2BC',
    'accent': '#E11D35',
    'blue': '#FA4357',  # nome legado usado por gráficos e KPIs
    'good': '#49DBA6',
    'warn': '#FFCA65',
    'bad': '#FF6171',
    'bad_bg': '#421D27',
    'warn_bg': '#46351E',
    'good_bg': '#1D4035',
    'bar_track': '#343640',
}

FCST_LABELS = {'pessoas': 'BBP', 'garantia': 'VLT TOTAL 2026'}

THRESHOLD_CRITICAL = 0.80
THRESHOLD_ATTENTION = 0.95


def destination_channel(area: Area, metric: str) -> str:
    """Emula a alternância de indicadores do arquivo original."""
    if metric in ('mes', 'fcst', 'percentual', 'falta') and area.secondary:
        return 'secondary'
    return 'primary'
