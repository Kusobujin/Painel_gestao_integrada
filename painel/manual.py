"""Lançamento manual em lote: cria competência e edita todos os indicadores.

Nenhum arquivo Excel é obrigatório. O formulário grava no SQLite já utilizado
pela tabela e pelo carrossel; os demais setores do mês são preservados.
"""
from __future__ import annotations

import re
import calendar
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk, simpledialog

from .date_picker import ask_date

from .config import AREAS, AREA_BY_KEY, C, ROWS, destination_channel
from .data import Snapshot
from .metrics import number
from .ui import ActionButton, dark_menu

FIELD_LABELS = {
    'dia': ('Valor do dia', 'Resultado ou previsão do dia selecionado'),
    'capacidade': ('Capacidade / saldo', 'Capacidade disponível ou saldo do setor'),
    'mes': ('Realizado no mês', 'Acumulado do mês até esta data'),
    'stk_pai': ('Estoque pai', 'Quantidade em estoque pai'),
    'stk_filho': ('Estoque filho', 'Quantidade em estoque filho'),
    'fcst': ('Meta do mês (FCST / BBP)', 'Meta ou previsão cadastrada para o mês'),
    'percentual': ('Atingimento (%)', 'Exemplo: 98,2 significa 98,2%'),
}

EDITABLE_ROWS = tuple((key, label) for key, label, _ in ROWS if key != 'falta')


def parse_manual_number(raw, is_percent=False):
    """Aceita 12000, 12.000, 12.000,5, 12000.5, 20,3%.

    Na coluna percentual, 20,3 equivale a 20,3%; 0,5 equivale a 0,5%.
    Por padrão '.' separando grupos de três é tratado como milhar em campos
    não-percentuais; para decimais use vírgula.
    """
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip().replace('R$', '').replace('%', '').replace(' ', '')
    if not text or re.search(r'[^+\-\d.,]', text):
        raise ValueError(f'Número inválido: {raw!r}')
    if ',' in text:
        if text.count(',') > 1:
            raise ValueError(f'Número inválido: {raw!r}')
        text = text.replace('.', '').replace(',', '.')
    elif '.' in text and not is_percent and re.fullmatch(r'[+\-]?\d{1,3}(?:\.\d{3})+', text):
        text = text.replace('.', '')
    val = number(text)
    if val is None:
        raise ValueError(f'Número inválido: {raw!r}')
    if is_percent:
        if val < 0:
            raise ValueError('Atingimento não pode ser negativo')
        return val / 100
    return val


def validate_competence(period, reference_date):
    if not re.fullmatch(r'\d{4}-\d{2}', period):
        raise ValueError('A competência deve ter o formato AAAA-MM, exemplo: 2026-10.')
    try:
        date.fromisoformat(period + '-01')
        ref = date.fromisoformat(reference_date)
    except ValueError as exc:
        raise ValueError('Data inválida. Use AAAA-MM-DD e uma competência existente.') from exc
    if ref.strftime('%Y-%m') != period:
        raise ValueError('A data de referência deve estar dentro do mês escolhido.')
    return ref


def save_manual_area(repo, period, reference_date, area_key, raw_values, auto_calculate=True):
    """Atualiza apenas um setor; salva todas as suas métricas em uma transação.

    raw_values = {'dia': {'primary': '42.000', 'secondary': '...'}, ...}
    Chaves ausentes preservam o valor anterior. Campos fornecidos vazios
    APAGAM intencionalmente seu valor; nunca apagamos outra área.
    """
    validate_competence(period, reference_date)
    area = repo.get_area(area_key)
    if area is None or not repo.is_area_visible(area_key):
        raise ValueError('Painel inexistente ou oculto. Habilite-o em Gerenciar painéis.')
    parsed = {}
    for metric, channels in raw_values.items():
        if metric not in dict(EDITABLE_ROWS):
            raise ValueError(f'Indicador desconhecido: {metric}')
        for channel, raw in channels.items():
            if channel not in ('primary', 'secondary') or (channel == 'secondary' and not area.secondary):
                raise ValueError('Subcoluna inválida para a área')
            try:
                value = parse_manual_number(raw, is_percent=metric == 'percentual')
            except ValueError as exc:
                label = dict(EDITABLE_ROWS)[metric]
                raise ValueError(f'{label} / {channel}: {exc}') from exc
            parsed.setdefault(metric, {})[channel] = value

    snap = repo.get(period) or Snapshot(period=period, reference_date=reference_date,
                                        source='MANUAL', areas={})
    day = repo.get_day(reference_date)
    # Cada data mantém números próprios. Não propaga valores de dias posteriores.
    info = {metric: dict(channels) for metric, channels in
            (day.areas.get(area_key, {}) if day else
             (snap.areas.get(area_key, {}) if snap.reference_date == reference_date else {})).items()}
    errors = {}
    if reference_date >= snap.reference_date:
        snap.reference_date = reference_date
    month_info = snap.areas.setdefault(area_key, {})
    snap.errors.setdefault(area_key, {})
    for metric, channels in parsed.items():
        info.setdefault(metric, {}).update(channels)
        errors.pop(metric, None)

    for channel in ('primary', 'secondary'):
        if channel == 'secondary' and not area.secondary:
            continue
        actual = info.get('mes', {}).get(channel)
        target = info.get('fcst', {}).get(channel)
        if auto_calculate and actual is not None and target not in (None, 0):
            attainment = actual / target
            info.setdefault('percentual', {})[channel] = attainment
            errors.pop('percentual', None)
        else:
            attainment = info.get('percentual', {}).get(channel)
        info.setdefault('falta', {})[channel] = max(0, 1 - attainment) if attainment is not None else None
        errors.pop('falta', None)

    if not errors:
        snap.errors.pop(area_key, None)
    # A fonte anterior fica preservada no texto, mas atualização do Excel deixa
    # de ocorrer para evitar que um clique em 'Atualizar' destrua edição local.
    old = snap.source
    if old.startswith('MANUAL • '):
        old = old[9:]
    snap.source = f'MANUAL • {old}' if old and old != 'MANUAL' else 'MANUAL'
    snap.file_path = ''
    # O mês guarda o último valor informado de cada métrica; dias têm registro independente.
    for metric in set(parsed) | {'percentual', 'falta'}:
        if metric in info:
            month_info.setdefault(metric, {}).update(info[metric])
    # Consolidação: se meta e realizado vêm de dias diferentes, o percentual
    # do mês precisa refletir ambos, sem alterar o histórico diário.
    for ch in ('primary', 'secondary'):
        if ch == 'secondary' and not area.secondary:
            continue
        actual = month_info.get('mes', {}).get(ch)
        target = month_info.get('fcst', {}).get(ch)
        if auto_calculate and actual is not None and target not in (None, 0):
            month_info.setdefault('percentual', {})[ch] = actual / target
        attainment = month_info.get('percentual', {}).get(ch)
        month_info.setdefault('falta', {})[ch] = max(0, 1 - attainment) if attainment is not None else None
    repo.save_area_with_day(snap, reference_date, area_key, info)
    return repo.get(period)


class ManualEntryDialog(tk.Toplevel):
    def __init__(self, parent, repo, initial_period=None, initial_area=None, on_save=None,
                 initial_date=None):
        super().__init__(parent)
        self.repo = repo
        self.on_save = on_save
        self.title('Phinia • Registrar dados')
        self.configure(bg=C['bg'])
        self.transient(parent)
        self.minsize(710, 580)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(940, sw-70), min(800, sh-100)
        self.geometry(f'{width}x{height}+{max(5, (sw-width)//2)}+{max(5, (sh-height)//2)}')
        self.areas = repo.list_areas()
        if not self.areas:
            raise ValueError('Nenhum painel ativo. Ative um em Gerenciar painéis.')
        chosen = next((a for a in self.areas if a.key == initial_area), self.areas[0])
        self.period_var = tk.StringVar(value=initial_period or date.today().strftime('%Y-%m'))
        self.area_var = tk.StringVar(value=chosen.short)
        default_day = (initial_date[-2:] if initial_date and initial_date.startswith(self.period_var.get() + '-')
                       else self._initial_day(self.period_var.get()))
        self.day_var = tk.StringVar(value=default_day)
        self.auto_var = tk.BooleanVar(value=True)
        self.details_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value='Pronto para preencher')
        self._dirty = False
        self._loading = False
        self._loaded_period = self.period_var.get()
        self._loaded_area = self.area_var.get()
        self._loaded_day = self.day_var.get()
        self.fields = {}
        self.holders = {}
        self.field_vars = {}
        self._baseline = {}
        self._build()
        self.bind('<Configure>', self._resize_dialog)
        self._load_values(force=True)
        self.grab_set()
        self.focus_set()
        self.bind('<Control-s>', lambda e: self._save(False))
        self.bind('<Escape>', lambda e: self._close())
        self.protocol('WM_DELETE_WINDOW', self._close)

    def _button(self, parent, text, cmd, primary=False):
        return ActionButton(parent, text, cmd, primary=primary, padx=14, pady=9)

    def _build(self):
        header = tk.Frame(self, bg=C['bg'])
        header.pack(fill='x', padx=26, pady=(20, 11))
        tk.Label(header, text='Registrar dados', font=('Segoe UI Semibold', 20, 'bold'),
                 fg=C['text'], bg=C['bg']).pack(anchor='w')
        tk.Label(header, text='1. Escolha o setor e a data.   2. Preencha os valores.   3. Salve.',
                 font=('Segoe UI', 10), fg=C['muted'], bg=C['bg']).pack(anchor='w', pady=(4, 0))

        selector = tk.Frame(self, bg=C['surface'], highlightbackground=C['stroke'], highlightthickness=1)
        selector.pack(fill='x', padx=26, pady=(0, 11))
        for col, (title, variable, width) in enumerate((
            ('MÊS (ANO-MÊS)', self.period_var, 14),
            ('SETOR', self.area_var, 22),
            ('DATA DO LANÇAMENTO', self.day_var, 12),
        )):
            cell = tk.Frame(selector, bg=C['surface'])
            cell.grid(row=0, column=col, sticky='w', padx=16, pady=12)
            tk.Label(cell, text=title, fg=C['muted'], bg=C['surface'],
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 5))
            if col == 0:
                widget = ttk.Combobox(cell, textvariable=variable, width=width,
                                      values=self._all_periods())
                widget.bind('<<ComboboxSelected>>', self._period_changed)
                widget.bind('<Return>', self._period_changed)
            elif col == 1:
                widget = ttk.Combobox(cell, textvariable=variable, width=width,
                                      values=[a.short for a in self.areas], state='readonly')
                widget.bind('<<ComboboxSelected>>', self._selection_changed)
            else:
                wrap = tk.Frame(cell, bg=C['surface'])
                wrap.pack()
                self.date_label_var = tk.StringVar()
                self.day_button = tk.Button(wrap, textvariable=self.date_label_var, command=self._pick_day,
                                            bg=C['surface_3'], fg=C['text'], activebackground=C['surface_2'],
                                            activeforeground=C['text'], relief='flat', bd=0,
                                            font=('Segoe UI', 10, 'bold'), padx=14, pady=7, cursor='hand2')
                self.day_button.pack(side='left')
                widget = None
            if widget is not None:
                widget.pack(ipady=4)
        selector.grid_columnconfigure(1, weight=1)

        section = tk.Frame(self, bg=C['surface'], highlightbackground=C['stroke'], highlightthickness=1)
        section.pack(fill='both', expand=True, padx=26, pady=(0, 9))
        self.source_label = tk.Label(section, text='', bg=C['surface'], fg=C['muted'],
                                     font=('Segoe UI', 9), anchor='w')
        self.source_label.pack(fill='x', padx=18, pady=(10, 3))
        self.primary_label = tk.StringVar()
        self.secondary_label = tk.StringVar()
        self.value_heading = tk.StringVar(value='VALOR')
        self.metric_heading = tk.StringVar(value='INDICADOR')
        headings = tk.Frame(section, bg=C['surface_2'])
        self.headings = headings
        headings.pack(fill='x', padx=14, pady=(6, 1))
        headings.grid_columnconfigure(0, weight=2)
        headings.grid_columnconfigure(1, weight=2)
        headings.grid_columnconfigure(2, weight=2)
        self.heading_widgets = []
        for col, var in enumerate((self.metric_heading, self.value_heading, self.secondary_label)):
            heading = tk.Label(headings, textvariable=var if isinstance(var, tk.StringVar) else None,
                     text=var if isinstance(var, str) else '', fg=C['text'], bg=C['surface_2'],
                     font=('Segoe UI', 10, 'bold'), anchor='w', wraplength=235,
                     justify='left')
            heading.grid(row=0, column=col, sticky='ew', padx=14, pady=8)
            self.heading_widgets.append(heading)

        scroller = tk.Frame(section, bg=C['surface'])
        scroller.pack(fill='both', expand=True, padx=14, pady=3)
        self.canvas = tk.Canvas(scroller, bg=C['surface'], bd=0, highlightthickness=0)
        scroll = ttk.Scrollbar(scroller, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.fields_frame = tk.Frame(self.canvas, bg=C['surface'])
        self.canvas_window = self.canvas.create_window((0,0), window=self.fields_frame, anchor='nw')
        self.fields_frame.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))
        self.canvas.bind('<MouseWheel>', self._scroll)
        self.fields_frame.grid_columnconfigure(0, weight=2)
        self.fields_frame.grid_columnconfigure(1, weight=2)
        self.fields_frame.grid_columnconfigure(2, weight=2)
        order = ('dia', 'mes', 'fcst', 'percentual', 'capacidade', 'stk_pai', 'stk_filho')
        for i, key in enumerate(order):
            bg = C['surface'] if i % 2 == 0 else C['stripe']
            label_frame = tk.Frame(self.fields_frame, bg=bg)
            label_frame.grid(row=i, column=0, sticky='nsew')
            tk.Label(label_frame, text=FIELD_LABELS[key][0], bg=bg, fg=C['text'],
                     font=('Segoe UI', 10, 'bold'), anchor='w').pack(fill='x', padx=13, pady=(8, 0))
            hint = tk.Label(label_frame, text=FIELD_LABELS[key][1], bg=bg, fg=C['muted'],
                            font=('Segoe UI', 9), anchor='w', justify='left', wraplength=290)
            hint.pack(fill='x', padx=13, pady=(0, 6))
            for widget in (label_frame, hint):
                widget.bind('<MouseWheel>', self._scroll)
            self.fields[key] = {}
            self.holders[key] = {}
            self.field_vars[key] = {}
            for col, channel in ((1, 'primary'), (2, 'secondary')):
                holder = tk.Frame(self.fields_frame, bg=bg)
                holder.grid(row=i, column=col, sticky='nsew')
                variable = tk.StringVar()
                entry = tk.Entry(holder, textvariable=variable, bg=C['surface_3'], fg=C['text'],
                                 disabledbackground=C['surface'], disabledforeground=C['muted'],
                                 insertbackground=C['text'], font=('Segoe UI', 12),
                                 justify='right', relief='flat', bd=0, width=18)
                entry.pack(fill='x', padx=10, pady=8, ipady=6)
                variable.trace_add('write', lambda *_: self._mark_dirty())
                entry.bind('<Return>', self._next_field)
                entry.bind('<MouseWheel>', self._scroll)
                entry.bind('<FocusIn>', self._reveal_field)
                self.fields[key][channel] = entry
                self.holders[key][channel] = holder
                self.field_vars[key][channel] = variable
        self.auto_box = tk.Checkbutton(section, text='Calcular o atingimento usando realizado e meta',
                                      variable=self.auto_var, bg=C['surface'], fg=C['text'],
                                      activebackground=C['surface'], activeforeground=C['text'],
                                      selectcolor=C['surface_3'], font=('Segoe UI', 10),
                                      command=self._mark_dirty)
        self.auto_box.pack(side='bottom', anchor='w', padx=20, pady=(3, 4), before=scroller)
        self.preview = tk.Label(section, text='', fg=C['muted'], bg=C['surface'],
                                font=('Segoe UI', 9), anchor='w')
        self.preview.pack(side='bottom', fill='x', padx=24, pady=(0, 8), before=self.auto_box)
        self.help = tk.Label(self, text='Use números como 1.250 ou 1.250,5. Campos não preenchidos preservam o mês; apagar um valor já carregado remove esse valor ao salvar.',
                             bg=C['bg'], fg=C['muted'], font=('Segoe UI', 9), anchor='w', wraplength=850)
        self.help.pack(side='bottom', fill='x', padx=27, pady=(0, 9), before=section)
        footer = tk.Frame(self, bg=C['bg'])
        footer.pack(side='bottom', fill='x', padx=26, pady=(0, 19), before=self.help)
        self.status_label = tk.Label(footer, textvariable=self.status_var, bg=C['bg'], fg=C['muted'],
                                     font=('Segoe UI', 10), anchor='w', wraplength=850)
        self.status_label.pack(fill='x', pady=(0, 8))
        actions = tk.Frame(footer, bg=C['bg'])
        actions.pack(fill='x')
        self.save_button = self._button(actions, 'Salvar dados', lambda: self._save(False), primary=True)
        self.save_button.pack(side='left', padx=(0, 8))
        self._button(actions, 'Salvar e próximo setor', lambda: self._save(True)).pack(side='left', padx=(0, 8))
        self._button(actions, 'Fechar', self._close).pack(side='right')
        self.options_button = self._button(actions, 'Mais opções', self._show_options)
        self.options_button.pack(side='right', padx=(0, 8))
        self.options_menu = dark_menu(self)
        self.options_menu.add_checkbutton(label='Mostrar duas colunas (avançado)', variable=self.details_var,
                                          command=self._apply_field_layout)
        self.options_menu.add_separator()
        self.options_menu.add_command(label='Limpar dados deste setor neste dia…', command=self._clear_day)
        self.options_menu.add_command(label='Limpar dados deste setor no mês…', command=self._clear_area)
        self.options_menu.add_separator()
        self.options_menu.add_command(label='Apagar todos os dados…', command=self._clear_all)

    def _show_options(self):
        self.options_menu.tk_popup(self.options_button.winfo_rootx(),
                                   self.options_button.winfo_rooty() + self.options_button.winfo_height())

    def _resize_dialog(self, event):
        if event.widget is self:
            width = max(180, event.width - 54)
            self.help.configure(wraplength=width)
            self.status_label.configure(wraplength=width)

    def _scroll(self, event):
        if self.fields_frame.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def _reveal_field(self, event):
        self.update_idletasks()
        top = event.widget.winfo_rooty() - self.fields_frame.winfo_rooty()
        height = max(1, self.fields_frame.winfo_height())
        first, last = self.canvas.yview()
        if top < first * height:
            self.canvas.yview_moveto(top / height)
        elif top + event.widget.winfo_height() > last * height:
            self.canvas.yview_moveto((top + event.widget.winfo_height() - self.canvas.winfo_height() + 12) / height)

    def _next_field(self, event):
        entries = [e for channels in self.fields.values() for e in channels.values()
                   if e.winfo_viewable() and e.cget('state') == 'normal']
        if event.widget in entries:
            index = entries.index(event.widget)
            if index + 1 < len(entries):
                entries[index + 1].focus_set()
                entries[index + 1].selection_range(0, 'end')
        return 'break'

    def _apply_field_layout(self):
        area = self._area()
        if not area:
            return
        detailed = self.details_var.get()
        self.metric_heading.set('INDICADOR')
        self.value_heading.set(area.primary.upper() if detailed else 'VALOR')
        if detailed:
            self.heading_widgets[2].grid()
        else:
            self.heading_widgets[2].grid_remove()
        self.fields_frame.columnconfigure(2, weight=2 if detailed else 0)
        self.headings.columnconfigure(2, weight=2 if detailed else 0)
        for metric, holders in self.holders.items():
            for channel, holder in holders.items():
                if detailed:
                    holder.grid(row=list(self.fields).index(metric), column=1 if channel == 'primary' else 2, sticky='nsew')
                elif channel == destination_channel(area, metric):
                    holder.grid(row=list(self.fields).index(metric), column=1, sticky='nsew')
                else:
                    holder.grid_remove()

    @staticmethod
    def _days_in_month(period):
        try:
            year, month = map(int, period.split('-'))
            total = calendar.monthrange(year, month)[1]
        except (ValueError, IndexError):
            return []
        return [f'{i:02d}' for i in range(1, total + 1)]

    def _initial_day(self, period):
        today = date.today()
        if today.strftime('%Y-%m') == period:
            return f'{today.day:02d}'
        existing = self.repo.available_days(period)
        if existing:
            return existing[0][-2:]
        snap = self.repo.get(period)
        if snap and snap.reference_date.startswith(period + '-'):
            return snap.reference_date[-2:]
        return '01'

    def _selected_date(self):
        return f'{self.period_var.get().strip()}-{self.day_var.get()}'

    def _pick_day(self):
        period = self.period_var.get().strip()
        initial = self._selected_date() if re.fullmatch(r'\d{4}-\d{2}', period) else None
        chosen = ask_date(self, initial_date=initial, period=period,
                          title='Selecionar dia do lançamento')
        if chosen:
            self.period_var.set(chosen[:7])
            self.day_var.set(chosen[-2:])
            self._selection_changed()


    def _all_periods(self):
        today = date.today().strftime('%Y-%m')
        return list(dict.fromkeys([today] + self.repo.periods()))

    def _area(self):
        return next((a for a in self.areas if a.short == self.area_var.get()), None)

    def _mark_dirty(self, _event=None):
        if not self._loading:
            self._dirty = True
            self.status_var.set('Alterações ainda não salvas • Ctrl+S para salvar')
            self.status_label.configure(fg=C['warn'])
            self._preview()

    def _period_changed(self, _event=None):
        period = self.period_var.get().strip()
        if re.fullmatch(r'\d{4}-\d{2}', period):
            try:
                date.fromisoformat(period + '-01')
                if period != self._loaded_period:
                    self.day_var.set(self._initial_day(period))
            except ValueError:
                pass
        self._load_values()

    def _selection_changed(self, _event=None):
        self._load_values()

    def _load_values(self, force=False):
        area = self._area()
        period = self.period_var.get().strip()
        if not area:
            return
        if not re.fullmatch(r'\d{4}-\d{2}', period):
            messagebox.showwarning('Competência inválida', 'Digite AAAA-MM, exemplo: 2026-10.', parent=self)
            return
        try:
            date.fromisoformat(period+'-01')
        except ValueError:
            messagebox.showwarning('Competência inválida', 'Mês inválido.', parent=self)
            return
        available = self._days_in_month(period)
        if not available:
            return
        if self.day_var.get() not in available:
            self.day_var.set(self._initial_day(period))
        if self._dirty and not force and (period, area.short, self.day_var.get()) != (self._loaded_period, self._loaded_area, self._loaded_day):
            if not messagebox.askyesno('Alterações não salvas',
                                      'Descartar as alterações deste setor sem salvar?', parent=self):
                self._loading = True
                self.period_var.set(self._loaded_period)
                self.area_var.set(self._loaded_area)
                self.day_var.set(self._loaded_day)
                self._loading = False
                return
        self._loading = True
        monthly = self.repo.get(period)
        reference = self._selected_date()
        snap = self.repo.get_day(reference)
        if snap is None and monthly and monthly.reference_date == reference:
            snap = monthly  # Compatibilidade com a planilha ou versão anterior.
        self._loaded_period = period
        self._loaded_area = area.short
        self._loaded_day = self.day_var.get()
        self.primary_label.set(area.primary.upper())
        self.secondary_label.set(area.secondary.upper() if area.secondary else 'NÃO SE APLICA')
        self.date_label_var.set(date.fromisoformat(reference).strftime('%d/%m/%Y') + '  ▾')
        values = snap.areas.get(area.key, {}) if snap else {}
        self.source_label.configure(text=f'{area.short} • ' +
                                    ('Valores já registrados nesta data' if values else 'Novo lançamento para esta data'))
        self.metric_heading.set('INDICADOR')
        self._baseline = {}
        for metric, channels in self.fields.items():
            for channel, entry in channels.items():
                entry.configure(state='normal', highlightthickness=1,
                                highlightbackground=C['accent'] if channel == destination_channel(area, metric) else C['stroke'],
                                highlightcolor=C['accent'])
                entry.delete(0, 'end')
                value = values.get(metric, {}).get(channel)
                if value is not None:
                    display = (value * 100) if metric == 'percentual' else value
                    entry.insert(0, f'{display:g}'.replace('.', ','))
                if channel == 'secondary' and not area.secondary:
                    entry.configure(state='disabled')
                self._baseline[(metric, channel)] = entry.get()
        self.auto_var.set(True)
        self._dirty = False
        self._loading = False
        self._apply_field_layout()
        self.status_var.set('Pronto para preencher • Ctrl+S para salvar')
        self.status_label.configure(fg=C['muted'])
        self.canvas.yview_moveto(0)
        self._preview()

    def _preview(self):
        area = self._area()
        if not area:
            return
        channel = 'secondary' if area.secondary else 'primary'
        for metric, channels in self.fields.items():
            for ch, entry in channels.items():
                try:
                    parse_manual_number(entry.get(), is_percent=metric == 'percentual')
                    color = C['stroke']
                except ValueError:
                    color = C['bad']
                entry.configure(highlightbackground=color, highlightcolor=C['accent'])
        try:
            raw_mes = self.fields['mes'][channel].get()
            raw_fcst = self.fields['fcst'][channel].get()
            actual = parse_manual_number(raw_mes)
            forecast = parse_manual_number(raw_fcst)
            if actual is not None and forecast not in (None, 0) and self.auto_var.get():
                pct = (actual / forecast) * 100
                self._loading = True
                self.field_vars['percentual'][channel].set(f'{pct:.2f}'.replace('.', ','))
                self._loading = False
                self.fields['percentual'][channel].configure(state='readonly', readonlybackground=C['surface_2'])
                self.preview.configure(text=(f'Atingimento calculado: {pct:.1f}% • Distância até a meta: {max(0, 100-pct):.1f}%').replace('.', ','), fg=C['good'])
            else:
                self.fields['percentual'][channel].configure(state='normal')
                self.preview.configure(text='Preencha realizado e meta para calcular o atingimento, ou informe o percentual.', fg=C['muted'])
        except ValueError:
            self.preview.configure(text='Confira os campos destacados antes de salvar.', fg=C['bad'])

    def _save(self, and_next):
        area = self._area()
        if not area:
            return
        if (self.period_var.get().strip(), area.short, self.day_var.get()) != (self._loaded_period, self._loaded_area, self._loaded_day):
            messagebox.showwarning('Carregue a competência',
                  'O período/setor foi alterado. Pressione Enter no mês ou selecione-o na lista antes de salvar.',
                  parent=self)
            return
        raw = {}
        for metric, channels in self.fields.items():
            for ch, entry in channels.items():
                include = ((ch == 'primary' or area.secondary) and
                           (self.details_var.get() or ch == destination_channel(area, metric) or
                            entry.get() != self._baseline.get((metric, ch), '')))
                if not include or (not entry.get().strip() and not self._baseline.get((metric, ch), '').strip()):
                    continue
                try:
                    parse_manual_number(entry.get(), is_percent=metric == 'percentual')
                except ValueError:
                    self.status_var.set(f'Confira {FIELD_LABELS[metric][0]}: digite um número como 1.250,5.')
                    self.status_label.configure(fg=C['bad'])
                    if not entry.winfo_viewable():
                        self.details_var.set(True)
                        self._apply_field_layout()
                    entry.focus_set()
                    entry.selection_range(0, 'end')
                    return
                raw.setdefault(metric, {})[ch] = entry.get()
        if not raw:
            self.status_var.set('Preencha pelo menos um valor antes de salvar.')
            self.status_label.configure(fg=C['warn'])
            return
        try:
            snap = save_manual_area(self.repo, self.period_var.get().strip(),
                                    self._selected_date(), area.key, raw, self.auto_var.get())
        except ValueError as exc:
            messagebox.showerror('Não foi possível salvar', str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror('Erro de armazenamento', str(exc), parent=self)
            return
        self._dirty = False
        self.source_label.configure(text='SALVO NO BANCO LOCAL • '+snap.imported_at)
        if self.on_save:
            self.on_save(snap.period)
        if and_next:
            index = self.areas.index(area)
            self.area_var.set(self.areas[(index+1) % len(self.areas)].short)
            self._load_values(force=True)
        else:
            self._load_values(force=True)
        self.status_var.set(f'Dados de {area.short} salvos • ' + date.fromisoformat(self._selected_date()).strftime('%d/%m/%Y'))
        self.status_label.configure(fg=C['good'])

    def _after_clearing(self):
        self._dirty = False
        if self.on_save:
            self.on_save(self.period_var.get().strip())
        self._load_values(force=True)

    def _clear_day(self):
        area = self._area()
        reference = self._selected_date()
        if not area:
            return
        if not messagebox.askyesno('Limpar somente o dia?',
                f'Apagar os registros de {area.short} em {reference}?\n'
                'Os outros dias e áreas permanecem. Um backup será criado.', parent=self):
            return
        try:
            backup = self.repo.clear_day_area(reference, area.key)
            self._after_clearing()
            messagebox.showinfo('Dia limpo', f'Backup: {backup}', parent=self)
        except Exception as exc:
            messagebox.showerror('Erro ao limpar dia', str(exc), parent=self)

    def _clear_area(self):
        area = self._area()
        month = self.period_var.get().strip()
        if not area:
            return
        if not messagebox.askyesno('Excluir área do mês?',
                f'Apagar TODOS os lançamentos de {area.short} no mês {month}?\n'
                'Inclui todos os dias desta área, mas preserva as demais áreas.\n'
                'Será criado um backup antes da exclusão.', parent=self):
            return
        try:
            backup = self.repo.clear_area_period(month, area.key)
            self._after_clearing()
            messagebox.showinfo('Área limpa', f'Backup: {backup}', parent=self)
        except Exception as exc:
            messagebox.showerror('Erro ao limpar área', str(exc), parent=self)

    def _clear_all(self):
        if not messagebox.askyesno('ATENÇÃO • Apagar toda a base?',
                'Isto apagará TODOS os meses, dias e áreas gravados neste computador.\n'
                'As preferências do carrossel serão mantidas.\n'
                'Um backup do banco será criado automaticamente.\n\nContinuar?',
                icon='warning', parent=self):
            return
        answer = simpledialog.askstring('Confirmação final',
                'Para confirmar a exclusão de todos os dados, digite APAGAR:', parent=self)
        if answer != 'APAGAR':
            return
        try:
            backup = self.repo.clear_all_data()
            self._after_clearing()
            messagebox.showinfo('Base limpa', f'Todos os lançamentos foram apagados.\nBackup: {backup}', parent=self)
        except Exception as exc:
            messagebox.showerror('Erro ao apagar dados', str(exc), parent=self)

    def _close(self):
        if self._dirty and not messagebox.askyesno('Alterações não salvas',
                    'Fechar sem salvar as alterações deste setor?', parent=self):
            return
        self.destroy()
