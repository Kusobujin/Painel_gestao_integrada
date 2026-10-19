"""Apresentação de gráficos com os controles e animações do ANDON."""
import tkinter as tk
import time
from collections import OrderedDict
from tkinter import ttk

from .carousel import CarouselPanel, paginate_areas, selected_areas, ease_in_out_cubic
from .charts import ChartPanel
from .config import C, AREAS
from .overview import display_date
from .metrics import get_value
from .ui import ActionButton, dark_menu


def chart_slides(areas, metrics, types):
    """Percentuais comparam setores; valores absolutos mantêm unidades separadas."""
    slides = []
    for metric in metrics:
        if metric not in ChartPanel.METRICS:
            continue
        for kind in types:
            if kind not in ChartPanel.TYPES:
                continue
            if kind == 'Distribuição de status' and metric != 'Atingimento (%)':
                continue
            groups = ([areas] if kind == 'Distribuição de status' else paginate_areas(areas, 8)) if (
                ChartPanel.METRICS[metric] in ('percentual', 'falta')) else [[area] for area in areas]
            for group in groups:
                if group:
                    slides.append((metric, kind, list(group)))
    return slides


class ChartCard(tk.Frame):
    def __init__(self, parent, slide, snapshot, on_menu, compact=False):
        super().__init__(parent, bg=C['surface'], highlightthickness=1, highlightbackground=C['stroke'])
        metric, kind, areas = slide
        tk.Frame(self, bg=C['accent'], height=4).pack(fill='x')
        tk.Label(self, text=metric, bg=C['surface'], fg=C['text'], anchor='w',
                 font=('Segoe UI', 14 if compact else 19, 'bold')).pack(fill='x', padx=18, pady=(8, 3))
        subtitle = kind + ' • ' + ('Nenhum setor ativo' if not areas else areas[0].short if len(areas) == 1 else f'{len(areas)} setores selecionados')
        tk.Label(self, text=subtitle, bg=C['surface'], fg=C['muted'], anchor='w',
                 font=('Segoe UI', 10)).pack(fill='x', padx=18, pady=(0, 4))
        self.plot = ChartPanel(self, presentation=True)
        self.plot.compact = compact
        self.plot.var_metric.set(metric)
        self.plot.var_type.set(kind)
        self.plot.pack(fill='both', expand=True)
        self._draw_job = self.after(100, lambda: self._draw(snapshot, areas))
        self.bind('<Destroy>', self._closed)
        self._bind_menu(self, on_menu)
        self.bind('<Configure>', lambda e: self.plot.note.configure(wraplength=max(120, e.width-44))
                  if e.widget is self else None)

    def _draw(self, snapshot, areas):
        self._draw_job = None
        self.plot.update_data(snapshot, areas)
        if not areas:
            self.plot.note.configure(text='Os setores deste gráfico estão ocultos ou indisponíveis.')
            if self.plot.plot_canvas:
                self.plot.plot_canvas.get_tk_widget().bind('<Button-3>', self._on_menu)
            return
        missing = sum(get_value(snapshot, a.key, ChartPanel.METRICS[self.plot.var_metric.get()], a) is None
                      for a in areas) if snapshot else len(areas)
        self.plot.note.configure(text=('Meta cadastrada • Sem ajuste pelo dia'
                                      if self.plot.var_metric.get() in ('Atingimento (%)', 'Falta (%)')
                                      else f'Indicador do setor • {areas[0].primary if ChartPanel.METRICS[self.plot.var_metric.get()] in ("dia", "capacidade", "stk_pai", "stk_filho") else areas[0].secondary or areas[0].primary}'))
        if missing:
            self.plot.note.configure(text=self.plot.note.cget('text') + f' • {missing} sem informação')
        if self.plot.var_type.get() == 'Linha comparativa':
            self.plot.note.configure(text='Comparação entre setores • Não representa histórico diário' +
                                     (f' • {missing} sem informação' if missing else ''))
        if self.plot.plot_canvas:
            self.plot.plot_canvas.get_tk_widget().bind('<Button-3>', self._on_menu)

    def _bind_menu(self, widget, on_menu):
        self._on_menu = on_menu
        widget.bind('<Button-3>', on_menu)
        for child in widget.winfo_children():
            self._bind_menu(child, on_menu)

    def _closed(self, event):
        if event.widget is self and self._draw_job:
            self.after_cancel(self._draw_job)
            self._draw_job = None


class ChartSettings(tk.Toplevel):
    def __init__(self, parent, panel):
        super().__init__(parent)
        self.withdraw()
        self.panel = panel
        self.title('Phinia • Configurar carrossel de gráficos')
        self.configure(bg=C['bg'])
        self.transient(parent.winfo_toplevel())
        self.minsize(600, 460)
        width, height = min(750, self.winfo_screenwidth()-60), min(700, self.winfo_screenheight()-100)
        self.geometry(f'{width}x{height}+{max(0,(self.winfo_screenwidth()-width)//2)}+{max(0,(self.winfo_screenheight()-height)//2)}')
        tk.Label(self, text='Configurar gráficos', bg=C['bg'], fg=C['text'],
                 font=('Segoe UI', 21, 'bold')).pack(anchor='w', padx=24, pady=(18, 5))
        tk.Label(self, text='Escolha os indicadores, os formatos e os setores para apresentar.',
                 bg=C['bg'], fg=C['muted'], font=('Segoe UI', 10)).pack(anchor='w', padx=24, pady=(0, 12))
        bottom = tk.Frame(self, bg=C['bg'])
        bottom.pack(side='bottom', fill='x', padx=24, pady=16)
        self.error = tk.Label(bottom, bg=C['bg'], fg=C['warn'], anchor='w')
        self.error.pack(fill='x', pady=(0, 6))
        self.apply_button = ActionButton(bottom, 'Aplicar e apresentar', self._apply, primary=True, padx=15, pady=10)
        self.apply_button.pack(side='left')
        ActionButton(bottom, 'Cancelar', self.destroy, padx=15, pady=10).pack(side='right')
        options = tk.Frame(self, bg=C['surface'])
        options.pack(fill='x', padx=24, pady=(0, 12))
        self.interval = tk.StringVar(value=panel.interval_var.get())
        self.size = tk.StringVar(value=panel.size_var.get())
        for col, (label, var, choices) in enumerate((('Tempo por tela', self.interval, list(panel.INTERVALS)),
                                                   ('Gráficos por tela', self.size, list(panel.PAGE_SIZES)))):
            cell = tk.Frame(options, bg=C['surface'])
            cell.grid(row=0, column=col, padx=14, pady=12)
            tk.Label(cell, text=label, bg=C['surface'], fg=C['muted']).pack(anchor='w')
            ttk.Combobox(cell, textvariable=var, values=choices, state='readonly', width=21).pack(pady=(5, 0))
        tabs = ttk.Notebook(self)
        tabs.pack(fill='both', expand=True, padx=24)
        self.metric_vars = self._checks(tabs, 'Indicadores', list(ChartPanel.METRICS), panel.metrics_selected)
        self.type_vars = self._checks(tabs, 'Tipos de gráfico', list(ChartPanel.TYPES), panel.types_selected)
        self.area_vars = self._checks(tabs, 'Setores', [a.key for a in panel._all_areas], panel.selected_keys,
                                     {a.key: a.short for a in panel._all_areas})
        tk.Label(self, text='Distribuição de status usa atingimento. Valores absolutos aparecem por setor.',
                 bg=C['bg'], fg=C['muted'], font=('Segoe UI', 9), wraplength=690, justify='left').pack(fill='x', padx=24, pady=8)
        self.bind('<Escape>', lambda _: self.destroy())
        self.deiconify()
        self.grab_set()

    def _checks(self, tabs, title, keys, chosen, labels=None):
        outer = tk.Frame(tabs, bg=C['surface'])
        tabs.add(outer, text=title)
        controls = tk.Frame(outer, bg=C['surface'])
        controls.pack(side='bottom', fill='x', padx=14, pady=10)
        canvas = tk.Canvas(outer, bg=C['surface'], highlightthickness=0)
        scroll = ttk.Scrollbar(outer, command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        content = tk.Frame(canvas, bg=C['surface'])
        window = canvas.create_window(0, 0, anchor='nw', window=content)
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
        content.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        def wheel(event):
            if content.winfo_height() > canvas.winfo_height():
                canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            return 'break'
        canvas.bind('<MouseWheel>', wheel)
        variables = {}
        for key in keys:
            variables[key] = tk.BooleanVar(value=key in chosen)
            box = tk.Checkbutton(content, text=(labels or {}).get(key, key), variable=variables[key],
                                 bg=C['surface'], fg=C['text'], selectcolor=C['surface_3'],
                                 activebackground=C['surface_2'], activeforeground=C['text'],
                                 font=('Segoe UI', 11), anchor='w', padx=12, pady=7)
            box.pack(fill='x')
            box.bind('<MouseWheel>', wheel)
        for text, value in (('Marcar todos', True), ('Desmarcar todos', False)):
            ActionButton(controls, text, lambda value=value: [v.set(value) for v in variables.values()],
                         padx=12, pady=7).pack(side='left', padx=(0, 8))
        return variables

    def _apply(self):
        metrics = [k for k, v in self.metric_vars.items() if v.get()]
        types = [k for k, v in self.type_vars.items() if v.get()]
        keys = [k for k, v in self.area_vars.items() if v.get()]
        if not metrics or not types or not keys:
            self.error.configure(text='Escolha pelo menos um indicador, um tipo de gráfico e um setor.')
            return
        if not chart_slides(selected_areas(self.panel._all_areas, keys), metrics, types):
            self.error.configure(text='Para distribuição de status, marque o indicador Atingimento (%).')
            return
        self.panel.metrics_selected, self.panel.types_selected = metrics, types
        self.panel.interval_var.set(self.interval.get())
        self.panel.size_var.set(self.size.get())
        hidden = [key for key in self.panel.selected_keys if key not in self.area_vars]
        self.panel.selected_keys = hidden + keys
        self.panel._rebuild()
        self.panel._persist()
        self.destroy()


class ChartCarouselPanel(CarouselPanel):
    PAGE_SIZES = {'1 gráfico': 1, '2 gráficos': 2, '3 gráficos': 3, '4 gráficos': 4}

    def __init__(self, parent, **kwargs):
        self._page_cache = OrderedDict()
        self._ready_job = None
        self._warm_job = None
        self._resize_job = None
        self._queued_move = 0
        self._host_size = None
        repo = kwargs.get('repository')
        cfg = repo.get_setting('chart_carousel', {}) if repo else {}
        if not isinstance(cfg, dict):
            cfg = {}
        self.metrics_selected = [m for m in cfg.get('metrics', ['Atingimento (%)', 'Falta (%)']) if m in ChartPanel.METRICS]
        self.types_selected = [t for t in cfg.get('types', ['Barras horizontais', 'Colunas']) if t in ChartPanel.TYPES]
        super().__init__(parent, **kwargs)
        self.selected_keys = cfg.get('areas', [a.key for a in (repo.list_areas(include_hidden=True) if repo else AREAS)])
        self.interval_var.set(cfg.get('interval') if cfg.get('interval') in self.INTERVALS else '10 s')
        self.size_var.set(cfg.get('size') if cfg.get('size') in self.PAGE_SIZES else '2 gráficos')
        self._remaining = float(self.interval_seconds)

    def _build(self):
        super()._build()

    def _cancel_job(self, name):
        job = getattr(self, name, None)
        if job:
            self.after_cancel(job)
            setattr(self, name, None)

    def _clear_cache(self):
        for name in ('_ready_job', '_warm_job', '_resize_job'):
            self._cancel_job(name)
        self._cancel_animation()
        self._queued_move = 0
        for frame in self._page_cache.values():
            if frame.winfo_exists():
                frame.destroy()
        self._page_cache.clear()
        if self._page_widget and self._page_widget.winfo_exists():
            self._page_widget.destroy()
        self._page_widget = None

    def _cached_page(self, index):
        if index not in self._page_cache:
            frame = self._new_page_widget(self.pages[index])
            frame._count = len(self.pages[index])
            self._position(frame, self.card_host.winfo_width()+40)
            self._page_cache[index] = frame
        self._page_cache.move_to_end(index)
        for key in list(self._page_cache):
            if len(self._page_cache) <= 5:
                break
            cached = self._page_cache[key]
            if key != index and cached not in (self._page_widget, self._incoming, self._outgoing):
                self._page_cache.pop(key).destroy()
        return self._page_cache[index]

    @staticmethod
    def _page_ready(frame):
        # Inclui o ajuste de margens e o desenho final do Matplotlib.
        return all(card._draw_job is None and card.plot._layout_job is None and
                   (card.plot.plot_canvas is None or not getattr(card.plot.plot_canvas, '_idle_draw_id', None))
                   for card in frame.winfo_children())

    def _warm_neighbors(self):
        self._warm_job = None
        if not self.active or not self.pages:
            return
        if self._animation_job or self._ready_job:
            self._warm_job = self.after(300, self._warm_neighbors)
            return
        keep = {self.index, (self.index+1) % len(self.pages), (self.index-1) % len(self.pages)}
        for key in list(self._page_cache):
            if key not in keep:
                self._page_cache.pop(key).destroy()
        # Uma página por etapa mantém o trabalho fora da animação.
        for key in ((self.index+1) % len(self.pages), (self.index-1) % len(self.pages)):
            if key not in self._page_cache:
                self._cached_page(key)
                self._warm_job = self.after(400, self._warm_neighbors)
                break

    def _render_page(self, animate=False, direction=1):
        self._stop_timer()
        self._cancel_job('_warm_job')
        if not self.pages:
            super()._render_page(False)
            return
        self._cancel_job('_ready_job')
        self._wait_for_page(self.index, animate, direction)

    def _wait_for_page(self, index, animate, direction):
        self._ready_job = None
        if self.card_host.winfo_width() < 200 or self.card_host.winfo_height() < 100:
            self._ready_job = self.after(30, lambda: self._wait_for_page(index, animate, direction))
            return
        frame = self._cached_page(index)
        if not all(self._page_ready(cached) for cached in self._page_cache.values()):
            self._ready_job = self.after(20, lambda: self._wait_for_page(index, animate, direction))
            return
        previous = self._page_widget
        self._page_widget = frame
        if animate and self.active and previous and previous is not frame:
            self._incoming, self._outgoing = frame, previous
            self._animation_start = time.monotonic()
            self._animation_direction = direction
            self._position(frame, direction*(self.card_host.winfo_width()+40))
            frame.lift()
            self._animate_pages()
        else:
            if previous and previous is not frame:
                previous.place_forget()
            self._position(frame)
            self._transition_finished()

    def _animate_pages(self):
        self._animation_job = None
        if self._incoming is None or self._outgoing is None:
            return
        t = min(1., (time.monotonic()-self._animation_start)/self.ANIMATION_SECONDS)
        offset = self._animation_direction*(self.card_host.winfo_width()+40)
        eased = ease_in_out_cubic(t)
        self._position(self._incoming, offset*(1-eased))
        self._position(self._outgoing, -offset*eased)
        if t >= 1:
            self._outgoing.place_forget()
            self._incoming = self._outgoing = None
            self._animation_start = None
            self._position(self._page_widget)
            self._transition_finished()
        else:
            self._animation_job = self.after(16, self._animate_pages)

    def _transition_finished(self):
        self._reset_timer()
        if self._queued_move:
            move, self._queued_move = self._queued_move, 0
            self._move(move)
        elif self.active:
            self._warm_job = self.after(600, self._warm_neighbors)

    def _cancel_animation(self):
        self._cancel_job('_animation_job')
        if self._outgoing and self._outgoing.winfo_exists():
            self._outgoing.place_forget()
        self._incoming = self._outgoing = None
        self._animation_start = None

    def _move(self, direction):
        if not self.pages:
            return
        if self._animation_job or self._ready_job:
            self._queued_move += direction
            return
        self.index = (self.index+direction) % len(self.pages)
        self._render_page(animate=len(self.pages)>1, direction=1 if direction>0 else -1)

    def _run_timer(self):
        if self._animation_job or self._ready_job:
            self._stop_timer()
            return
        super()._run_timer()

    def _resize(self, event=None):
        size = (self.card_host.winfo_width(), self.card_host.winfo_height())
        if size == self._host_size:
            return
        self._host_size = size
        self._stop_timer()
        self._cancel_job('_ready_job')
        self._cancel_job('_warm_job')
        self._cancel_animation()
        self._position(self._page_widget)
        if self.active:
            self._cancel_job('_resize_job')
            self._resize_job = self.after(180, self._rebuild_after_resize)

    def _rebuild_after_resize(self):
        self._resize_job = None
        self._clear_cache()
        if self.active:
            self._render_page()

    def _on_destroy(self, event):
        if event.widget is self:
            for name in ('_ready_job', '_warm_job', '_resize_job'):
                self._cancel_job(name)
            super()._on_destroy(event)

    def _persist(self):
        if self.repository:
            self.repository.set_setting('chart_carousel', {
                'metrics': self.metrics_selected, 'types': self.types_selected, 'areas': self.selected_keys,
                'interval': self.interval_var.get(), 'size': self.size_var.get()})

    def _rebuild(self, keep_index=False):
        self._clear_cache()
        self.areas = selected_areas(self._all_areas, self.selected_keys)
        self.pages = paginate_areas(chart_slides(self.areas, self.metrics_selected, self.types_selected), self.page_size)
        self.index = min(self.index, max(0, len(self.pages)-1)) if keep_index else 0
        if self.active:
            self._render_page()
        self._reset_timer()

    def update_data(self, snapshot, areas):
        self.snapshot, self._all_areas = snapshot, list(areas)
        self.reference_label.configure(text=f'GRÁFICOS • {snapshot.period if snapshot else "Sem dados"}\nReferência: {display_date(snapshot.reference_date) if snapshot else "Não informada"}')
        self._rebuild(keep_index=True)

    def set_active(self, active):
        if not active:
            for name in ('_ready_job', '_warm_job', '_resize_job'):
                self._cancel_job(name)
            self._queued_move = 0
        if active and not self.active:
            self._render_page()
        super().set_active(active)

    def _view_geometry(self, n):
        return 8, 4, max(1, self.card_host.winfo_width()-16), max(1, self.card_host.winfo_height()-8)

    def _new_page_widget(self, page):
        frame = tk.Frame(self.card_host, bg=C['bg'])
        columns = 1 if len(page) == 1 else 2
        for i, slide in enumerate(page):
            ChartCard(frame, slide, self.snapshot, self.show_options, compact=len(page)>2).grid(row=i//columns, column=i%columns,
                sticky='nsew', padx=6, pady=6)
            frame.columnconfigure(i%columns, weight=1, uniform='graphs')
            frame.rowconfigure(i//columns, weight=1, uniform='graphs')
        return frame

    def set_page_size(self, count):
        if count not in self.PAGE_SIZES.values():
            raise ValueError('Quantidade inválida de gráficos')
        self.size_var.set(next(k for k, value in self.PAGE_SIZES.items() if value == count))
        self._rebuild()
        self._persist()

    def set_interval(self, seconds):
        super().set_interval(seconds)
        self._persist()

    def set_visible_areas(self, keys):
        allowed = {a.key for a in self._all_areas}
        if any(key not in allowed for key in keys):
            raise ValueError('Área desconhecida')
        self.selected_keys = [key for key in self.selected_keys if key not in allowed] + list(dict.fromkeys(keys))
        self._rebuild()
        self._persist()

    def open_settings(self):
        was_active = self.active
        self.set_active(False)
        win = ChartSettings(self, self)
        win.bind('<Destroy>', lambda e: self.set_active(True)
                 if e.widget is win and was_active and self.winfo_exists() and self.winfo_manager() and self.master.winfo_manager() else None)
        return win

    def show_options(self, event=None):
        menu = dark_menu(self)
        menu.add_command(label='Configurar indicadores, gráficos e setores…', command=self.open_settings)
        menu.add_command(label='Escolher setores…', command=self.open_area_chooser)
        menu.add_separator()
        menu.add_command(label='Pausar' if self.playing else 'Retomar', command=self.toggle_play)
        menu.add_command(label='Anterior', command=self.previous)
        menu.add_command(label='Próxima', command=self.next)
        for label, values, command in (('Gráficos por tela', (1, 2, 3, 4), self.set_page_size),
                                       ('Tempo por tela', (5, 10, 15, 30, 60), self.set_interval)):
            sub = dark_menu(menu)
            for value in values:
                sub.add_command(label=f'{value} {"gráfico(s)" if label == "Gráficos por tela" else "segundos"}',
                                command=lambda v=value, cmd=command: cmd(v))
            menu.add_cascade(label=label, menu=sub)
        menu.add_separator()
        menu.add_command(label='Tela cheia / F11', command=self.on_fullscreen)
        menu.add_command(label='Voltar ao painel / F9', command=self.on_exit)
        try:
            menu.tk_popup(event.x_root if event else self.winfo_rootx()+40,
                          event.y_root if event else self.winfo_rooty()+80)
        finally:
            menu.grab_release()
