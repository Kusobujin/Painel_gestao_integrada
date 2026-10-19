"""Carrossel ANDON imersivo: cartões + temporizador, sem cabeçalho.

Mudança de páginas com slide/easing em Tkinter; relógio monotônico e after()
para progresso fluido. O carrossel mostra dados locais; não consulta SAP.
Controles ocultos em menu do botão direito e atalhos de teclado.
"""
from __future__ import annotations

import math
import time
import tkinter as tk
from tkinter import ttk

from .assets import assets, LOGO_PATH, BANNER_PATH
from .config import C, AREAS
from .metrics import fmt_cell, get_value, status_of
from .overview import display_date
from .ui import ActionButton


METRIC_CARDS = (
    ('dia', 'DIA'), ('capacidade', 'CAP. / SALDO'),
    ('mes', 'MÊS REALIZADO'), ('fcst', 'META / FCST'),
    ('stk_pai', 'ESTOQUE PAI'), ('stk_filho', 'ESTOQUE FILHO'),
    ('falta', 'FALTA %'),
)


def paginate_areas(areas, page_size):
    if not isinstance(page_size, int) or page_size < 1:
        raise ValueError('A quantidade de áreas por página deve ser positiva')
    return [list(areas[i:i + page_size]) for i in range(0, len(areas), page_size)]


def status_presentation(attainment):
    return {
        'no_alvo': ('NO ALVO', C['good'], C['good_bg']),
        'atencao': ('ATENÇÃO', C['warn'], C['warn_bg']),
        'critico': ('CRÍTICO', C['bad'], C['bad_bg']),
        'sem_dados': ('SEM DADOS', C['muted'], C['surface_3']),
    }[status_of(attainment)]


def ease_in_out_cubic(t):
    """Suaviza a entrada/saída sem depender de bibliotecas externas."""
    t = max(0., min(1., float(t)))
    return 4 * t ** 3 if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def centered_group_geometry(container_width, num_cards):
    """Retorna (x, width): principalmente 2 cartões centralizados na TV."""
    width = max(200, int(container_width))
    if num_cards == 1:
        group = min(width - 16, 600)
    elif num_cards == 2:
        group = min(width - 16, 1240, int(width * .82))
    elif num_cards == 3:
        group = min(width - 16, 1700)
    else:
        group = min(width - 16, 1900)
    return (width - group) // 2, max(180, group)


class Gauge(tk.Canvas):
    def __init__(self, parent, value, color):
        super().__init__(parent, bg=C['surface'], bd=0, highlightthickness=0, height=16)
        self.value = value
        self.color = color
        self.bind('<Configure>', self._draw)

    def _draw(self, _event=None):
        self.delete('all')
        w = max(2, self.winfo_width())
        self.create_rectangle(0, 3, w, 12, fill=C['bar_track'], outline='')
        if self.value is not None and math.isfinite(self.value):
            self.create_rectangle(0, 3, w * max(0., min(self.value, 1.)), 12,
                                  fill=self.color, outline='')
            target = w * .95
            self.create_line(target, 1, target, 14, fill=C['text'], width=2)


class AreaCard(tk.Frame):
    """Um setor. Duplo clique abre formulário manual daquele setor."""
    def __init__(self, parent, area, snapshot, on_edit=None, on_menu=None, large=False, card_width=380):
        super().__init__(parent, bg=C['surface'], highlightbackground=C['stroke'], highlightthickness=1)
        pct = get_value(snapshot, area.key, 'percentual', area) if snapshot else None
        wrap_width = max(250, min(520, int(card_width) - 54))
        header_size = 19 if large else 16
        pct_size = 48 if large else 40
        metric_size = 12 if large else 11
        value_size = 16 if large else 14
        state, color, state_bg = status_presentation(pct)
        tk.Frame(self, height=5, bg=C['accent']).pack(fill='x')
        heading = tk.Frame(self, bg=C['surface'])
        heading.pack(fill='x', padx=20, pady=(17, 5))
        tk.Label(heading, text=area.short.upper(), fg=C['text'], bg=C['surface'],
                 font=('Segoe UI Semibold', header_size, 'bold'), anchor='w',
                 wraplength=wrap_width, justify='left').pack(anchor='w')
        desc = area.primary + (f'   /   {area.secondary}' if area.secondary else '')
        tk.Label(heading, text=desc, fg=C['muted'], bg=C['surface'],
                 font=('Segoe UI', 9), anchor='w', wraplength=wrap_width,
                 justify='left').pack(anchor='w', pady=(3, 0))
        top = tk.Frame(self, bg=C['surface'])
        top.pack(fill='x', padx=20, pady=(11, 0))
        tk.Label(top, text='ATINGIMENTO', bg=C['surface'], fg=C['muted'],
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        percentage = fmt_cell(pct, 'percentual', area.key)
        if snapshot and snapshot.errors.get(area.key, {}).get('percentual') and pct is None:
            percentage = 'ERRO'
        tk.Label(top, text=percentage, bg=C['surface'], fg=color,
                 font=('Segoe UI Semibold', pct_size, 'bold')).pack(anchor='w', pady=(1, 0))
        tk.Label(top, text=state, bg=state_bg, fg=color,
                 font=('Segoe UI', 9, 'bold'), padx=13, pady=5).pack(anchor='w', pady=(0, 9))
        Gauge(top, pct, color).pack(fill='x')
        tk.Label(top, text='FAIXA DE 95% • SEM AJUSTE PELO DIA', bg=C['surface'], fg=C['muted'],
                 font=('Segoe UI', 8)).pack(anchor='w', pady=(3, 9))
        tk.Frame(self, height=1, bg=C['stroke']).pack(fill='x', padx=20, pady=(0, 4))
        rows = tk.Frame(self, bg=C['surface'])
        rows.pack(fill='both', expand=True, padx=20, pady=(0, 6))
        for idx, (metric, title) in enumerate(METRIC_CARDS):
            if idx == 6:
                tk.Frame(rows, height=1, bg=C['stroke']).pack(fill='x', pady=(4, 4))
            line = tk.Frame(rows, bg=C['surface'])
            line.pack(fill='x', pady=3, expand=True)
            val = get_value(snapshot, area.key, metric, area) if snapshot else None
            error = snapshot.errors.get(area.key, {}).get(metric) if snapshot else None
            show = 'ERRO' if error and val is None else fmt_cell(val, metric, area.key)
            val_color = C['bad'] if error and val is None else (C['accent'] if metric == 'falta' else C['text'])
            tk.Label(line, text=title, fg=C['muted'], bg=C['surface'],
                     font=('Segoe UI', metric_size, 'bold'), anchor='w').pack(side='left')
            tk.Label(line, text=show, fg=val_color, bg=C['surface'],
                     font=('Segoe UI Semibold', value_size, 'bold'), anchor='e').pack(side='right')
        tk.Label(self, text='— = valor não informado', bg=C['surface'], fg=C['muted'],
                 font=('Segoe UI', 9)).pack(anchor='w', padx=20, pady=(0, 13))
        self._bind_events(self, on_edit, on_menu, area.key)

    def _bind_events(self, widget, on_edit, on_menu, area_key):
        if on_edit:
            widget.bind('<Double-Button-1>', lambda e: on_edit(area_key))
        if on_menu:
            widget.bind('<Button-3>', on_menu)
        for child in widget.winfo_children():
            self._bind_events(child, on_edit, on_menu, area_key)


def selected_areas(all_areas, selected_keys):
    """Mantém a ordem operacional original e respeita o conjunto marcado."""
    wanted = set(selected_keys)
    return [area for area in all_areas if area.key in wanted]


class AreaChooser(tk.Toplevel):
    """Janela de checkboxes dedicada aos setores visíveis no ANDON."""
    def __init__(self, parent, initially_selected, on_apply, areas):
        super().__init__(parent)
        self.withdraw()
        self.title('ANDON • Áreas visíveis no carrossel')
        self.configure(bg=C['bg'])
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.minsize(560, 390)
        self.choices = list(areas)
        self.vars = {a.key: tk.BooleanVar(value=a.key in initially_selected) for a in self.choices}
        tk.Label(self, text='SELECIONAR ÁREAS DO CARROSSEL', bg=C['bg'], fg=C['text'],
                 font=('Segoe UI Semibold', 17, 'bold')).pack(anchor='w', padx=25, pady=(22, 6))
        tk.Label(self, text='Marque apenas os setores que deseja apresentar no telão.\n'
                            'A ordem acompanha o painel gerencial e fica salva no computador.',
                 bg=C['bg'], fg=C['muted'], font=('Segoe UI', 10),
                 justify='left').pack(anchor='w', padx=25, pady=(0, 15))
        wrapper = tk.Frame(self, bg=C['surface'])
        wrapper.pack(fill='both', padx=25, pady=(0, 13), expand=True)
        canvas = tk.Canvas(wrapper, bg=C['surface'], borderwidth=0, highlightthickness=0,
                           width=550, height=min(450, 45 * max(1, (len(self.choices)+1)//2)))
        scroll = ttk.Scrollbar(wrapper, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        frame = tk.Frame(canvas, bg=C['surface'])
        window = canvas.create_window((0,0), window=frame, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        def scroll_wheel(event):
            if frame.winfo_height() > canvas.winfo_height():
                canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            return 'break'
        canvas.bind('<MouseWheel>', scroll_wheel)
        for i, area in enumerate(self.choices):
            box = tk.Checkbutton(frame, text=area.short, variable=self.vars[area.key],
                                 bg=C['surface'], fg=C['text'], selectcolor=C['surface_3'],
                                 activebackground=C['surface'], activeforeground=C['text'],
                                 font=('Segoe UI', 11), anchor='w',
                                 command=self._update_count)
            box.grid(row=i//2, column=i%2, padx=17, pady=10, sticky='w')
            box.bind('<MouseWheel>', scroll_wheel)
        frame.grid_columnconfigure(0, weight=1, uniform='areas')
        frame.grid_columnconfigure(1, weight=1, uniform='areas')
        controls = tk.Frame(self, bg=C['bg'])
        controls.pack(side='bottom', fill='x', padx=25, before=wrapper)
        tk.Button(controls, text='MARCAR TODAS', command=lambda: self._set_all(True),
                  bg=C['surface_3'], fg=C['text'], bd=0, padx=13, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(controls, text='DESMARCAR TODAS', command=lambda: self._set_all(False),
                  bg=C['surface_3'], fg=C['text'], bd=0, padx=13, pady=7).pack(side='left')
        self.counter = tk.Label(controls, bg=C['bg'], fg=C['muted'], font=('Segoe UI', 10))
        self.counter.pack(side='right')
        self._update_count()
        bottom = tk.Frame(self, bg=C['bg'])
        bottom.pack(side='bottom', fill='x', padx=25, pady=(12, 20), before=controls)
        self.apply_button = ActionButton(bottom, 'Aplicar seleção', lambda: self._apply(on_apply),
                                         primary=True, padx=19, pady=10)
        self.apply_button.pack(side='left')
        ActionButton(bottom, 'Cancelar', self.destroy, padx=18, pady=10).pack(side='right')
        self.grab_set()
        self.focus_set()
        self.bind('<Escape>', lambda _: self.destroy())
        self.update_idletasks()
        width = min(690, self.winfo_screenwidth() - 60)
        height = min(580, self.winfo_screenheight() - 100)
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f'{width}x{height}+{max(x,0)}+{max(y,0)}')
        self.deiconify()

    def _update_count(self):
        self.counter.configure(text=f'{sum(bool(v.get()) for v in self.vars.values())}/{len(self.choices)} selecionadas')

    def _set_all(self, value):
        for var in self.vars.values():
            var.set(value)
        self._update_count()

    def _apply(self, callback):
        callback([a.key for a in self.choices if self.vars[a.key].get()])
        self.destroy()


class CarouselPanel(tk.Frame):
    INTERVALS = {'5 s': 5, '10 s': 10, '15 s': 15, '30 s': 30, '60 s': 60}
    PAGE_SIZES = {'2 áreas': 2, '3 áreas': 3, '4 áreas': 4}
    ANIMATION_SECONDS = .48
    TIMER_TICK_MS = 25

    def __init__(self, parent, on_exit=None, on_fullscreen=None, on_edit=None, on_manage=None, repository=None):
        super().__init__(parent, bg=C['bg'])
        self.on_exit = on_exit
        self.on_fullscreen = on_fullscreen
        self.on_edit = on_edit
        self.on_manage = on_manage
        self.repository = repository
        self.banner_img = assets.photo('carousel_banner', BANNER_PATH, max_width=310, max_height=48, master=self)
        self.logo_img = assets.photo('carousel_logo', LOGO_PATH, max_width=48, max_height=40, master=self)
        stored = repository.get_setting('carousel_area_selection', None) if repository else None
        initial_areas = repository.list_areas(include_hidden=True) if repository else AREAS
        self.selected_keys = [a.key for a in initial_areas] if stored is None else list(dict.fromkeys(stored))
        self.snapshot = None
        self._all_areas = []
        self.areas = []
        self.pages = []
        self.index = 0
        self.playing = True
        self.active = False
        self._job = None
        self._animation_job = None
        self._deadline = None
        self._remaining = 10.
        self._page_widget = None
        self._incoming = None
        self._outgoing = None
        self._animation_start = None
        self.interval_var = tk.StringVar(value='10 s')
        self.size_var = tk.StringVar(value='3 áreas')
        self._build()
        self.bind('<Destroy>', self._on_destroy)

    @property
    def interval_seconds(self):
        return self.INTERVALS[self.interval_var.get()]

    @property
    def page_size(self):
        return self.PAGE_SIZES[self.size_var.get()]

    def _build(self):
        # Branding em uma faixa própria, fora da camada dos cards deslizantes.
        # Assim o logotipo nunca fica atrás de uma página do carrossel.
        self.brand_bar = tk.Frame(self, bg=C['bg'], height=62)
        self.brand_bar.pack(fill='x', padx=20, pady=(5, 0))
        self.brand_bar.pack_propagate(False)
        brand = tk.Frame(self.brand_bar, bg=C['bg'])
        brand.pack(side='right', anchor='e', pady=5)
        if self.banner_img:
            tk.Label(brand, image=self.banner_img, bg=C['bg']).pack(side='left', padx=(0, 17))
        tk.Frame(brand, bg=C['stroke'], width=1, height=34).pack(side='left', padx=(0, 14))
        if self.logo_img:
            tk.Label(brand, image=self.logo_img, bg=C['bg']).pack(side='left')
        tk.Label(brand, text='PHINIA', bg=C['bg'], fg=C['text'],
                 font=('Segoe UI Semibold', 22, 'bold')).pack(side='left', padx=(7, 0))
        self.reference_label = tk.Label(self.brand_bar, bg=C['bg'], fg=C['muted'],
                                       font=('Segoe UI', 10), anchor='w', justify='left')
        self.reference_label.pack(side='left', fill='x', expand=True)
        self.card_host = tk.Frame(self, bg=C['bg'])
        self.card_host.pack(fill='both', expand=True, padx=12, pady=(2, 2))
        self.card_host.bind('<Configure>', self._resize)
        self.lower = tk.Frame(self, bg=C['bg'], height=38)
        self.lower.pack(fill='x', padx=20, pady=(0, 11))
        self.time_label = tk.Label(self.lower, text='00:10  •  01/04', bg=C['bg'],
                                   fg=C['muted'], font=('Segoe UI', 10, 'bold'), anchor='e')
        self.time_label.pack(fill='x', pady=(0, 7))
        self.progress = tk.Canvas(self.lower, height=6, bd=0, highlightthickness=0,
                                  bg=C['bar_track'])
        self.progress.pack(fill='x')
        self.progress_track = self.progress.create_rectangle(0, 0, 0, 6, fill=C['accent'], outline='')
        self.progress.bind('<Configure>', lambda _: self._paint_progress())
        for item in (self, self.brand_bar, brand, self.card_host, self.lower, self.time_label, self.progress):
            item.bind('<Button-3>', self.show_options)

    def _on_destroy(self, event):
        if event.widget is self:
            self._stop_timer()
            self._cancel_animation()

    def _stop_timer(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _cancel_animation(self):
        if self._animation_job is not None:
            try:
                self.after_cancel(self._animation_job)
            except tk.TclError:
                pass
            self._animation_job = None
        for frame in (self._outgoing, self._incoming):
            if frame and frame is not self._page_widget and frame.winfo_exists():
                frame.destroy()
        self._outgoing = None
        self._incoming = None
        self._animation_start = None

    def _reset_timer(self):
        self._remaining = float(self.interval_seconds)
        self._deadline = time.monotonic() + self._remaining
        self._run_timer()

    def _run_timer(self):
        self._stop_timer()
        self._paint_progress()
        if self.active and self.playing and len(self.pages) > 1:
            self._deadline = time.monotonic() + self._remaining
            self._job = self.after(self.TIMER_TICK_MS, self._tick_timer)

    def _tick_timer(self):
        self._job = None
        if not self.active or not self.playing or len(self.pages) <= 1:
            return
        self._remaining = max(0., self._deadline - time.monotonic())
        self._paint_progress()
        if self._remaining <= 0:
            self.next()
        else:
            self._job = self.after(self.TIMER_TICK_MS, self._tick_timer)

    def _paint_progress(self):
        duration = float(self.interval_seconds)
        if len(self.pages) <= 1:
            portion, remaining = 1., duration
        else:
            remaining = self._remaining
            if self.active and self.playing and self._deadline is not None:
                remaining = max(0., self._deadline - time.monotonic())
            portion = max(0., min(1., (duration - remaining) / duration))
        self.progress.coords(self.progress_track, 0, 0,
                             int(self.progress.winfo_width() * portion), 6)
        count = len(self.pages)
        self.time_label.configure(text=f'{int(math.ceil(remaining)):02d}s  •  {self.index+1:02d}/{count:02d}'
                                  if count else 'SEM DADOS')

    def _view_geometry(self, n):
        width = max(1, self.card_host.winfo_width())
        height = max(1, self.card_host.winfo_height())
        x, group_w = centered_group_geometry(width, n)
        group_h = min(height - 8, 785)
        return x, max(2, (height - group_h) // 2), group_w, max(1, group_h)

    def _new_page_widget(self, page):
        frame = tk.Frame(self.card_host, bg=C['bg'])
        count = len(page)
        group_width = centered_group_geometry(max(1, self.card_host.winfo_width()), count)[1]
        individual_width = max(180, group_width / count - 14)
        for col in range(count):
            frame.grid_columnconfigure(col, weight=1, uniform='cards')
        frame.grid_rowconfigure(0, weight=1)
        for col, area in enumerate(page):
            card = AreaCard(frame, area, self.snapshot, on_edit=self.on_edit,
                            on_menu=self.show_options, large=(count <= 2),
                            card_width=individual_width)
            card.grid(row=0, column=col, padx=7, pady=1, sticky='nsew')
            card.bind('<Button-3>', self.show_options)
        frame.bind('<Button-3>', self.show_options)
        return frame

    def _position(self, frame, x_offset=0):
        if not frame or not frame.winfo_exists():
            return
        count = int(getattr(frame, '_count', 1))
        x, y, w, h = self._view_geometry(count)
        frame.place(x=x + int(x_offset), y=y, width=w, height=h)

    def _resize(self, _event=None):
        # A faixa de marca é independente dos cards e nunca é coberta.
        if self._animation_job is not None:
            self._cancel_animation()
        self._position(self._page_widget)

    def _render_page(self, animate=False, direction=1):
        self._cancel_animation()
        previous = self._page_widget
        if not self.pages:
            if previous and previous.winfo_exists():
                previous.destroy()
            label = tk.Label(self.card_host, text='NENHUMA ÁREA SELECIONADA.\n\n'
                          'F8 / botão direito → Escolher áreas.\n'
                          'Use F6 para lançar novos dados.',
                          bg=C['bg'], fg=C['muted'], font=('Segoe UI', 19), justify='center')
            label._count = 1
            self._page_widget = label
            self._position(label)
            self._paint_progress()
            return
        new = self._new_page_widget(self.pages[self.index])
        new._count = len(self.pages[self.index])
        self._page_widget = new
        if not animate or not self.active or not previous or not previous.winfo_exists():
            if previous and previous.winfo_exists():
                previous.destroy()
            self._position(new)
            self._paint_progress()
            return
        self._incoming = new
        self._outgoing = previous
        self._animation_start = time.monotonic()
        self._animation_direction = direction
        travel = self.card_host.winfo_width() + 40
        self._position(new, direction * travel)
        self._position(previous)
        new.lift()
        self._animate_pages()
        self._paint_progress()

    def _animate_pages(self):
        self._animation_job = None
        if self._incoming is None or self._outgoing is None:
            return
        t = (time.monotonic() - self._animation_start) / self.ANIMATION_SECONDS
        eased = ease_in_out_cubic(t)
        travel = self.card_host.winfo_width() + 40
        offset = self._animation_direction * travel
        self._position(self._incoming, offset * (1 - eased))
        self._position(self._outgoing, -offset * eased)
        if t >= 1.0:
            self._outgoing.destroy()
            self._outgoing = None
            self._incoming = None
            self._animation_start = None
            self._position(self._page_widget)
        else:
            self._animation_job = self.after(16, self._animate_pages)

    def update_data(self, snapshot, areas):
        self.reference_label.configure(text=(f'Referência do conjunto: {display_date(snapshot.reference_date)}\n'
            f'Registro: {display_date(snapshot.imported_at)}' if snapshot else 'Sem dados na seleção'))
        previous_identity = (self.snapshot.period if self.snapshot else '', tuple(a.key for a in self.areas))
        identity = (snapshot.period if snapshot else '', tuple(a.key for a in selected_areas(areas, self.selected_keys)))
        self.snapshot = snapshot
        self._all_areas = list(areas)
        self.areas = selected_areas(self._all_areas, self.selected_keys)
        self.pages = paginate_areas(self.areas, self.page_size)
        if previous_identity != identity or self.index >= len(self.pages):
            self.index = 0
        self._render_page()
        self._reset_timer()

    def set_active(self, active):
        if self.active == active:
            return
        if not active and self.active and self.playing and self._deadline is not None:
            self._remaining = max(0., self._deadline - time.monotonic())
        self.active = active
        if active:
            self._run_timer()
        else:
            self._stop_timer()
            self._cancel_animation()
            self._position(self._page_widget)
            self._paint_progress()

    def _move(self, direction):
        if self.pages:
            self.index = (self.index + direction) % len(self.pages)
            self._render_page(animate=len(self.pages) > 1, direction=direction)
        self._reset_timer()

    def next(self):
        self._move(1)

    def previous(self):
        self._move(-1)

    def toggle_play(self):
        if self.playing:
            if self.active and self._deadline is not None:
                self._remaining = max(0., self._deadline - time.monotonic())
            self.playing = False
            self._stop_timer()
        else:
            self.playing = True
            self._run_timer()
        self._paint_progress()

    def set_visible_areas(self, keys):
        allowed = {a.key for a in self._all_areas}
        if any(key not in allowed for key in keys):
            raise ValueError('Área desconhecida')
        # Seleções de setores ocultos ficam guardadas para um possível retorno.
        previous_hidden = [k for k in self.selected_keys if k not in allowed]
        self.selected_keys = list(dict.fromkeys(previous_hidden + list(keys)))
        if self.repository:
            self.repository.set_setting('carousel_area_selection', self.selected_keys)
        self.areas = selected_areas(self._all_areas, self.selected_keys)
        self.pages = paginate_areas(self.areas, self.page_size)
        self.index = 0
        self._render_page()
        self._reset_timer()

    def open_area_chooser(self):
        was_active = self.active
        self.set_active(False)
        win = AreaChooser(self, self.selected_keys, self.set_visible_areas, self._all_areas)
        win.bind('<Destroy>', lambda e: self.set_active(True)
                 if e.widget is win and was_active and self.winfo_exists() and self.winfo_manager() and self.master.winfo_manager() else None)
        return win

    def set_page_size(self, count):
        if count not in self.PAGE_SIZES.values():
            raise ValueError('Quantidade inválida de cartões')
        self.size_var.set(next(k for k,v in self.PAGE_SIZES.items() if v == count))
        self.pages = paginate_areas(self.areas, count)
        self.index = 0
        self._render_page()
        self._reset_timer()

    def set_interval(self, seconds):
        if seconds not in self.INTERVALS.values():
            raise ValueError('Intervalo inválido')
        self.interval_var.set(next(k for k,v in self.INTERVALS.items() if v == seconds))
        self._reset_timer()

    def show_options(self, event=None):
        """Controles acessíveis sem poluir o telão; botão direito ou F8."""
        menu = tk.Menu(self, tearoff=0, bg=C['surface'], fg=C['text'],
                       activebackground=C['accent'], activeforeground=C['text'],
                       borderwidth=1, relief='flat')
        menu.add_command(label='❚❚ Pausar' if self.playing else '▶ Retomar', command=self.toggle_play)
        menu.add_command(label='◀ Anterior', command=self.previous)
        menu.add_command(label='Próxima ▶', command=self.next)
        menu.add_separator()
        per_screen = tk.Menu(menu, tearoff=0, bg=C['surface'], fg=C['text'],
                             activebackground=C['accent'], activeforeground=C['text'])
        for n in (2, 3, 4):
            per_screen.add_radiobutton(label=f'{n} cartões', value=f'{n} áreas',
                                       variable=self.size_var, command=lambda n=n: self.set_page_size(n))
        menu.add_cascade(label='Cartões por tela', menu=per_screen)
        interval_menu = tk.Menu(menu, tearoff=0, bg=C['surface'], fg=C['text'],
                                activebackground=C['accent'], activeforeground=C['text'])
        for secs in (5, 10, 15, 30, 60):
            interval_menu.add_radiobutton(label=f'{secs} segundos', value=f'{secs} s',
                                          variable=self.interval_var,
                                          command=lambda v=secs: self.set_interval(v))
        menu.add_cascade(label='Tempo por tela', menu=interval_menu)
        menu.add_separator()
        menu.add_command(label='☑ Escolher áreas do carrossel...', command=self.open_area_chooser)
        if self.on_manage:
            menu.add_command(label='▤ Gerenciar painéis (criar, ocultar, renomear)...', command=self.on_manage)
        if self.on_edit:
            menu.add_command(label='✎ Lançamento manual (F6)', command=lambda: self.on_edit(None))
        if self.on_fullscreen:
            menu.add_command(label='Tela cheia (F11)', command=self.on_fullscreen)
        if self.on_exit:
            menu.add_command(label='Voltar ao painel (F9)', command=self.on_exit)
        x = event.x_root if event else self.winfo_rootx() + self.winfo_width() // 2
        y = event.y_root if event else self.winfo_rooty() + 80
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()
