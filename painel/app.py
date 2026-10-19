"""Orquestração da interface do Painel de Gestão Integrada."""
import csv
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .assets import assets, LOGO_PATH, BANNER_PATH
from .charts import ChartPanel
from .carousel import CarouselPanel
from .chart_carousel import ChartCarouselPanel
from .custom_carousel import CustomCarouselPanel
from .layout_editor import LayoutEditor
from .layouts import LayoutStore
from .date_picker import CONSOLIDATED, ask_date
from .manual import ManualEntryDialog, save_manual_area
from .area_manager import AreaManagerDialog
from .config import C, ROWS, ROW_GROUPS
from .data import ExcelGerencialAdapter, SQLiteSnapshotRepository
from .metrics import business_days, fmt_cell, fmt_number, number, set_value, summary
from .table import IndustrialGrid
from .overview import OverviewPanel, display_date
from .ui import ActionButton, dark_menu


class KpiCard(tk.Frame):
    def __init__(self, parent, title, color, **kwargs):
        super().__init__(parent, bg=C['surface'], highlightthickness=1,
                         highlightbackground=C['stroke'], **kwargs)
        self._color = color
        tk.Frame(self, bg=color, height=3).pack(fill='x')
        tk.Label(self, text=title, fg=C['muted'], bg=C['surface'],
                 anchor='w', font=('Segoe UI', 10)).pack(fill='x', padx=15, pady=(8, 0))
        self.value = tk.Label(self, text='—', fg=color, bg=C['surface'],
                              anchor='w', font=('Segoe UI Semibold', 24, 'bold'))
        self.value.pack(fill='x', padx=15, pady=(0, 1))
        self.caption = tk.Label(self, text='', fg=C['muted'], bg=C['surface'],
                                anchor='w', font=('Segoe UI', 9))
        self.caption.pack(fill='x', padx=15, pady=(0, 8))

    def update_value(self, value, caption):
        self.value.configure(text=value)
        self.caption.configure(text=caption)


class DashboardApp(tk.Tk):
    """Aplicação Tkinter, independente do formato e do provedor de dados."""
    def __init__(self, repository=None):
        super().__init__()
        self.title('Phinia | Painel de Gestão Integrada')
        self.geometry('1600x900')
        self.minsize(1060, 660)
        self.configure(bg=C['bg'])
        self.repo = repository or SQLiteSnapshotRepository()
        demo_path = Path(__file__).resolve().parent.parent / 'data' / 'exemplo_gerencial.json'
        self.repo.seed_if_empty(demo_path)
        self.period_var = tk.StringVar(value=(self.repo.periods() or [date.today().strftime('%Y-%m')])[0])
        self.all_areas = self.repo.list_areas(include_hidden=True)
        self.visible_areas = self.repo.list_areas()
        self.day_filter_var = tk.StringVar(value='Consolidado')
        self.area_var = tk.StringVar(value='Todas as áreas')
        self.metric_var = tk.StringVar(value='Todos')
        self.mode_var = tk.StringVar(value='Detalhado')
        self.snapshot = self.repo.get(self.period_var.get())
        self.sidebar_visible = True
        self.is_fullscreen = False
        self.presentation_mode = False
        self.presentation_kind = 'cards'
        self.logo_img = assets.photo('sidebar_logo', LOGO_PATH, max_width=74, max_height=40, master=self)
        self.header_banner_img = assets.photo('header_banner', BANNER_PATH, max_width=440, max_height=64, master=self)
        self._clock_job = None
        self._notice_job = None
        self.nav_buttons = {}
        self._setup_styles()
        self._build_ui()
        self._refresh()
        self._tick()
        self.bind('<F11>', lambda _: self.toggle_fullscreen())
        self.bind('<F9>', lambda _: self.toggle_carousel())
        self.bind('<F6>', lambda _: self.open_manual_entry())
        self.bind('<F8>', lambda _: self.open_carousel_settings())
        for n in (2, 3, 4):
            self.bind(str(n), lambda e, n=n: self._set_carousel_size(e, n))
        self.bind('<Left>', lambda event: self._carousel_key(event, 'previous'))
        self.bind('<Right>', lambda event: self._carousel_key(event, 'next'))
        self.bind('<space>', lambda event: self._carousel_key(event, 'toggle_play'))
        self.bind('<Escape>', self._escape)
        self.protocol('WM_DELETE_WINDOW', self.destroy)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TCombobox', background=C['surface_3'],
                        foreground=C['text'], fieldbackground=C['surface_3'],
                        selectbackground=C['surface_3'], selectforeground=C['text'],
                        bordercolor=C['stroke'], arrowsize=13, padding=5)
        style.map('TCombobox', fieldbackground=[('readonly', C['surface_3'])],
                  foreground=[('readonly', C['text'])])
        style.configure('TScrollbar', background=C['surface_3'], troughcolor=C['sidebar'],
                        bordercolor=C['sidebar'], arrowcolor=C['muted'])
        style.configure('TNotebook', background=C['bg'], bordercolor=C['bg'],
                        lightcolor=C['bg'], darkcolor=C['bg'],
                        borderwidth=0, relief='flat', padding=0)
        style.configure('TNotebook.Client', background=C['surface'], borderwidth=0, relief='flat', padding=0)
        style.configure('TNotebook.Tab', background=C['surface'], foreground=C['muted'],
                        font=('Segoe UI', 10, 'bold'), padding=(18, 10), borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', C['surface_3'])],
                  foreground=[('selected', C['text'])])

    def _button(self, parent, title, command, filled=False, padx=14, pady=10, **opts):
        return ActionButton(parent, title, command, primary=filled, padx=padx, pady=pady, **opts)

    def _sidebar_button(self, label, command):
        btn = self._button(self.sidebar, label, command, padx=16, pady=8)
        btn.configure(anchor='w', width=19)
        btn.pack(fill='x', padx=14, pady=4)
        return btn

    def _nav_section(self, title):
        tk.Label(self.sidebar, text=title, bg=C['sidebar'], fg=C['muted'],
                 font=('Segoe UI', 8, 'bold'), anchor='w').pack(fill='x', padx=22, pady=(12, 4))

    def _update_navigation(self):
        key = self.tabs.select()
        for target, button in self.nav_buttons.items():
            button.set_selected(target == key)

    def _show_tools(self):
        self.tools_menu.tk_popup(self.tools_button.winfo_rootx(),
                                 self.tools_button.winfo_rooty() + self.tools_button.winfo_height())

    def _show_presentations(self):
        menu = dark_menu(self)
        menu.add_command(label='Carrossel de indicadores', command=self.open_carousel)
        menu.add_command(label='Carrossel de gráficos', command=self.open_chart_carousel)
        custom = dark_menu(menu)
        custom.add_command(label='Montar / editar layouts…', command=self.open_layout_editor)
        custom.add_command(label='Apresentar carrossel personalizado', command=self.open_custom_carousel,
                           state='normal' if any(layout.get('enabled', True) for layout in LayoutStore(self.repo).load()) else 'disabled')
        menu.add_cascade(label='Layouts personalizados', menu=custom)
        try:
            menu.tk_popup(self.presentation_button.winfo_rootx(),
                          self.presentation_button.winfo_rooty()+self.presentation_button.winfo_height())
        finally:
            menu.grab_release()

    def _active_carousel(self):
        return {'cards': self.carousel_panel, 'charts': self.chart_carousel,
                'custom': self.custom_carousel}[self.presentation_kind]

    def open_layout_editor(self):
        active = self._active_carousel()
        was_active = self.presentation_mode
        if was_active:
            active.set_active(False)
        win = LayoutEditor(self, self.repo, self.snapshot, self.visible_areas,
                           on_save=self._layouts_saved, on_present=self.open_custom_carousel)
        win.bind('<Destroy>', lambda e: active.set_active(True)
                 if e.widget is win and was_active and self.presentation_mode and self._active_carousel() is active else None)
        return win

    def _layouts_saved(self):
        self.custom_carousel.update_data(self.snapshot, self.visible_areas)
        self._notify('Layouts personalizados salvos.')

    def _fit_sidebar(self, event):
        if event.height < 740:
            self.legend.pack_forget()
        elif not self.legend.winfo_manager():
            self.legend.pack(fill='x', before=self.data_mode_label)

    def _notify(self, message):
        if self._notice_job:
            self.after_cancel(self._notice_job)
        self.footer_left.configure(text=message, fg=C['good'])
        self._notice_job = self.after(6500, self._dismiss_notice)

    def _dismiss_notice(self):
        self._notice_job = None
        self.footer_left.configure(fg=C['muted'])
        self._refresh()

    def _reset_filters(self):
        self.area_var.set('Todas as áreas')
        self.metric_var.set('Todos')
        self.day_filter_var.set(CONSOLIDATED)
        self.mode_var.set('Detalhado')
        self._refresh()
        self._notify('Filtros limpos. Exibindo todos os setores deste mês.')

    def _show_help(self):
        win = tk.Toplevel(self)
        win.title('Como usar o painel')
        win.configure(bg=C['surface'])
        win.transient(self)
        win.geometry('590x560')
        win.minsize(540, 530)
        tk.Label(win, text='Como usar o painel', bg=C['surface'], fg=C['text'],
                 font=('Segoe UI', 20, 'bold')).pack(anchor='w', padx=24, pady=(22, 14))
        for title, detail in (
            ('Registrar dados', 'Escolha o setor e a data, preencha os valores e clique em Salvar dados. Ctrl+S também salva.'),
            ('Consultar resultados', 'Use Visão geral, Indicadores ou Gráficos. Os filtros escolhem o mês, o setor e o dia.'),
            ('Resumo do mês', 'Consolidado mostra os últimos valores informados. Para consultar um dia, clique na data.'),
            ('Apresentar no telão', 'Em Modo apresentação, escolha indicadores ou gráficos. Espaço pausa, setas trocam páginas e F8 configura.'),
            ('Montar uma apresentação', 'Em Layouts personalizados, arraste gráficos e indicadores, escolha os setores e clique em Salvar e apresentar.'),
            ('Outras ferramentas', 'Em Mais opções ficam importação de Excel, exportação, cadastro de setores e tela cheia.'),
        ):
            tk.Label(win, text=title, bg=C['surface'], fg=C['text'], font=('Segoe UI', 11, 'bold'),
                     anchor='w').pack(fill='x', padx=24, pady=(6, 0))
            tk.Label(win, text=detail, bg=C['surface'], fg=C['muted'], font=('Segoe UI', 10),
                     wraplength=535, justify='left', anchor='w').pack(fill='x', padx=24)
        self._button(win, 'Entendi', win.destroy, filled=True).pack(anchor='e', padx=24, pady=16)
        win.bind('<Escape>', lambda _: win.destroy())
        return win

    def _build_ui(self):
        self.body = tk.Frame(self, bg=C['bg'])
        self.body.pack(fill='both', expand=True)
        self.sidebar = tk.Frame(self.body, bg=C['sidebar'], width=220)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        brand = tk.Frame(self.sidebar, bg=C['sidebar'])
        brand.pack(fill='x', padx=18, pady=(18, 10))
        brand_line = tk.Frame(brand, bg=C['sidebar'])
        brand_line.pack(anchor='w')
        if self.logo_img:
            tk.Label(brand_line, image=self.logo_img, bg=C['sidebar']).pack(side='left', anchor='w')
            tk.Label(brand_line, text='PHINIA', bg=C['sidebar'], fg=C['text'],
                     font=('Segoe UI Semibold', 24, 'bold')).pack(side='left', padx=(10, 0), anchor='w')
        else:
            tk.Label(brand_line, text='PHINIA', bg=C['sidebar'], fg=C['text'],
                     font=('Segoe UI Semibold', 30, 'bold')).pack(side='left', anchor='w')
        tk.Frame(self.sidebar, height=1, bg=C['stroke']).pack(fill='x', padx=20, pady=(8, 16))
        self._nav_section('ACOMPANHAR')
        self.overview_nav = self._sidebar_button('Visão geral', lambda: self.tabs.select(self.tab_overview))
        self.grid_nav = self._sidebar_button('Indicadores', lambda: self.tabs.select(self.tab_grid))
        self.charts_nav = self._sidebar_button('Gráficos', lambda: self.tabs.select(self.tab_charts))
        self._nav_section('DIA A DIA')
        self._sidebar_button('Registrar dados', self.open_manual_entry)
        self.presentation_button = self._sidebar_button('Modo apresentação  ▾', self._show_presentations)
        self._sidebar_button('Recarregar dados', self.refresh_source)
        self._nav_section('FERRAMENTAS')
        self.tools_button = self._sidebar_button('Mais opções  ▾', self._show_tools)
        self._sidebar_button('Como usar', self._show_help)
        self.tools_menu = dark_menu(self)
        self.tools_menu.add_command(label='Gerenciar setores…', command=self.open_area_manager)
        self.tools_menu.add_command(label='Importar planilha Excel…', command=self.import_excel)
        self.tools_menu.add_command(label='Exportar indicadores…', command=self.export_csv)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label='Tela cheia / F11', command=self.toggle_fullscreen)
        tk.Frame(self.sidebar, bg=C['sidebar']).pack(fill='both', expand=True)
        self.legend = tk.Frame(self.sidebar, bg=C['sidebar'])
        self.legend.pack(fill='x')
        tk.Label(self.legend, text='LEGENDA DE ATINGIMENTO', fg=C['muted'], bg=C['sidebar'],
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=20, pady=(0, 8))
        for color, title in ((C['good'], '≥ 95%   No alvo'),
                             (C['warn'], '80–<95%   Atenção'),
                             (C['bad'], '< 80%   Crítico')):
            tk.Label(self.legend, text='●  ' + title, fg=color, bg=C['sidebar'],
                     font=('Segoe UI', 10)).pack(anchor='w', padx=20, pady=2)
        self.data_mode_label = tk.Label(self.sidebar, text='Dados salvos neste computador', fg=C['muted'],
                                        bg=C['sidebar'], font=('Segoe UI', 9))
        self.data_mode_label.pack(anchor='w', padx=20, pady=(16, 16))
        self.sidebar.bind('<Configure>', self._fit_sidebar)

        self.main = tk.Frame(self.body, bg=C['bg'])
        self.main.pack(side='left', fill='both', expand=True)
        self.topbar = tk.Frame(self.main, bg=C['bg'])
        top = self.topbar
        top.pack(fill='x', padx=20, pady=(17, 9))
        self._button(top, '☰', self.toggle_sidebar, padx=14, pady=9).pack(side='left', padx=(0, 14))
        titles = tk.Frame(top, bg=C['bg'])
        titles.pack(side='left', fill='x', expand=True)
        if self.header_banner_img:
            tk.Label(titles, image=self.header_banner_img, bg=C['bg']).pack(anchor='w')
        else:
            tk.Label(titles, text='PAINEL DE GESTÃO INTEGRADA', fg=C['text'], bg=C['bg'],
                     font=('Segoe UI Semibold', 21, 'bold'), anchor='w').pack(anchor='w')
            ####tk.Label(titles, text='Controle industrial • Operação, manufatura e gestão',
                ####     fg=C['muted'], bg=C['bg'], font=('Segoe UI', 10)).pack(anchor='w')
        self._button(top, 'Registrar dados', self.open_manual_entry, filled=True).pack(side='right', padx=(8, 0))

        self.kpi_bar = tk.Frame(self.main, bg=C['bg'])
        kpis = self.kpi_bar
        kpis.pack(fill='x', padx=20, pady=(3, 15))
        self.kpis = [
            KpiCard(kpis, 'ÁREAS', C['text']),
            KpiCard(kpis, 'NO ALVO (≥95%)', C['good']),
            KpiCard(kpis, 'ATENÇÃO', C['warn']),
            KpiCard(kpis, 'CRÍTICO', C['bad']),
            KpiCard(kpis, 'SEM ATINGIMENTO', C['muted']),
        ]
        for idx, card in enumerate(self.kpis):
            kpis.columnconfigure(idx, weight=1, uniform='kpi')
            card.grid(row=0, column=idx, sticky='ew', padx=(0 if idx == 0 else 8, 0))

        self.toolbar = tk.Frame(self.main, bg=C['surface'], highlightbackground=C['stroke'], highlightthickness=1)
        self.toolbar.pack(fill='x', padx=20, pady=(0, 8))
        toolbar = tk.Frame(self.toolbar, bg=C['surface'])
        toolbar.pack(fill='x')
        self.period_combo = self._filter_combo(toolbar, 'MÊS', self.period_var, self.repo.periods(), 11)
        self.area_combo = self._filter_combo(toolbar, 'ÁREA', self.area_var,
                      ['Todas as áreas'] + [area.short for area in self.visible_areas], 23)
        self.metric_combo = self._filter_combo(toolbar, 'INDICADORES', self.metric_var, list(ROW_GROUPS), 21)
        self.mode_combo = self._filter_combo(toolbar, 'VISUALIZAÇÃO', self.mode_var, ['Detalhado', 'Telão'], 13)
        self.period_combo.bind('<<ComboboxSelected>>', self._period_changed)
        for widget in (self.area_combo, self.metric_combo, self.mode_combo):
            widget.bind('<<ComboboxSelected>>', self._filter_changed)
        actions = tk.Frame(self.toolbar, bg=C['surface'])
        actions.pack(fill='x')
        self._button(actions, 'Limpar filtros', self._reset_filters, padx=11, pady=6).pack(side='right', padx=12, pady=(0, 8))

        self.source_line = tk.Frame(self.main, bg=C['bg'])
        source_line = self.source_line
        source_line.pack(fill='x', padx=23, pady=(0, 5))
        self.source_label = tk.Label(source_line, text='', anchor='w', fg=C['muted'],
                                     bg=C['bg'], font=('Segoe UI', 9))
        self.source_label.pack(side='left', fill='x', expand=True)
        self.alert_label = tk.Label(source_line, text='', anchor='e', fg=C['warn'],
                                    bg=C['bg'], font=('Segoe UI', 9, 'bold'))
        self.alert_label.pack(side='right', padx=(5, 0))
        self.day_filter_button = tk.Button(source_line, textvariable=self.day_filter_var,
                                           command=self._pick_filter_day,
                                           bg=C['surface_3'], fg=C['text'], activebackground=C['surface_2'],
                                           activeforeground=C['text'], relief='flat', bd=0,
                                           font=('Segoe UI', 9, 'bold'), padx=12, pady=5, cursor='hand2')
        self.day_filter_button.pack(side='right', padx=(8, 4))
        tk.Button(source_line, text='📅', command=self._pick_filter_day,
                  bg=C['surface_3'], fg=C['text'], activebackground=C['surface_2'],
                  activeforeground=C['text'], relief='flat', bd=0, padx=9, pady=5,
                  font=('Segoe UI', 9), cursor='hand2').pack(side='right', padx=(0, 4))
        tk.Label(source_line, text='CONSULTAR DIA:', bg=C['bg'], fg=C['muted'],
                 font=('Segoe UI', 9, 'bold')).pack(side='right')

        self.tabs = ttk.Notebook(self.main)
        self.tabs.pack(fill='both', expand=True, padx=20, pady=(0, 12))
        self.tab_overview = tk.Frame(self.tabs, bg=C['surface'])
        self.tab_grid = tk.Frame(self.tabs, bg=C['surface'])
        self.tab_charts = tk.Frame(self.tabs, bg=C['surface'])
        self.tabs.add(self.tab_overview, text='▦  Visão geral')
        self.overview_panel = OverviewPanel(self.tab_overview, self._open_area_details)
        self.overview_panel.pack(fill='both', expand=True)
        self.tabs.add(self.tab_grid, text='Indicadores')
        self.tabs.add(self.tab_charts, text='Gráficos')
        self.nav_buttons = {str(self.tab_overview): self.overview_nav,
                            str(self.tab_grid): self.grid_nav, str(self.tab_charts): self.charts_nav}
        self._update_navigation()
        self.grid_widget = IndustrialGrid(self.tab_grid, on_edit=self.edit_value)
        self.grid_widget.pack(fill='both', expand=True)
        self.chart_panel = ChartPanel(self.tab_charts, on_present=self.open_chart_carousel)
        self.chart_panel.pack(fill='both', expand=True)
        # Carrossel é uma vista completamente imersiva, fora do Notebook:
        # tabs + cabeçalho + rodapé são escondidos durante a apresentação.
        self.presentation_view = tk.Frame(self.main, bg=C['bg'])
        self.carousel_panel = CarouselPanel(self.presentation_view,
                                            on_exit=self.close_carousel,
                                            on_fullscreen=self.toggle_fullscreen,
                                            on_edit=self.open_manual_entry,
                                            on_manage=self.open_area_manager,
                                            repository=self.repo)
        self.carousel_panel.pack(fill='both', expand=True)
        self.chart_carousel = ChartCarouselPanel(self.presentation_view,
                                                on_exit=self.close_carousel,
                                                on_fullscreen=self.toggle_fullscreen,
                                                on_edit=self.open_manual_entry,
                                                on_manage=self.open_area_manager,
                                                repository=self.repo)
        self.custom_carousel = CustomCarouselPanel(self.presentation_view,
                                                  on_exit=self.close_carousel,
                                                  on_fullscreen=self.toggle_fullscreen,
                                                  on_editor=self.open_layout_editor,
                                                  repository=self.repo)
        self.tabs.bind('<<NotebookTabChanged>>', self._tab_changed)

        bottom = tk.Frame(self.main, bg=C['sidebar'], height=40)
        self.bottom_bar = bottom
        bottom.pack(side='bottom', fill='x', before=self.tabs)
        self.footer_left = tk.Label(bottom, bg=C['sidebar'], fg=C['muted'],
                                    font=('Segoe UI', 9), anchor='w')
        self.footer_left.pack(side='left', padx=18, pady=9)
        self.clock = tk.Label(bottom, bg=C['sidebar'], fg=C['text'],
                              font=('Segoe UI', 10, 'bold'), anchor='e')
        self.clock.pack(side='right', padx=20, pady=8)

    def _filter_combo(self, parent, title, variable, values, width):
        wrap = tk.Frame(parent, bg=C['surface'])
        wrap.pack(side='left', padx=(12, 0), pady=6)
        tk.Label(wrap, text=title, fg=C['muted'], bg=C['surface'],
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        combo = ttk.Combobox(wrap, textvariable=variable, state='readonly',
                             values=values, width=width)
        combo.pack(pady=(3, 2))
        return combo

    def _current_areas(self):
        label = self.area_var.get()
        return [a for a in self.visible_areas if label in ('', 'Todas as áreas', a.short)]

    def _current_rows(self):
        keys = ROW_GROUPS.get(self.metric_var.get(), ROW_GROUPS['Todos'])
        return [r for r in ROWS if r[0] in keys]

    def _open_area_details(self, area_key):
        area = next((a for a in self.visible_areas if a.key == area_key), None)
        if area:
            self.area_var.set(area.short)
            self.metric_var.set('Todos')
            self._refresh()
            self.tabs.select(self.tab_grid)

    def _refresh(self):
        # A data escolhida no calendário é válida mesmo sem lançamento.
        # Evita voltar silenciosamente ao consolidado ao escolher outro dia/mês.
        chosen = self.day_filter_var.get()
        if chosen == 'Consolidado':
            self.snapshot = self.repo.get(self.period_var.get())
        else:
            self.snapshot = self.repo.get_day(datetime.strptime(chosen, '%d/%m/%Y').date().isoformat())
        filtered = self._current_areas()
        stats = summary(self.snapshot, [a.key for a in filtered], filtered) if self.snapshot else None
        if stats:
            self.kpis[0].update_value(str(stats['areas']), 'No filtro atual')
            self.kpis[1].update_value(str(stats['good']), 'Da meta cadastrada')
            self.kpis[2].update_value(str(stats['warning']), 'De 80% a < 95%')
            self.kpis[3].update_value(str(stats['critical']), 'Abaixo de 80%')
            self.kpis[4].update_value(str(stats['missing']), 'Sem atingimento')
            warning_count = sum(len(self.snapshot.errors.get(a.key, {})) for a in filtered)
            demo = 'EXEMPLO • ' if self.snapshot.source.upper().startswith('EXEMPLO') else ''
            self.source_label.configure(text=f"{demo}Referência: {display_date(self.snapshot.reference_date)}",
                                        fg=C['warn'] if demo else C['muted'])
            self.alert_label.configure(text=f'⚠ {warning_count} erro(s) na origem' if warning_count else '')
            try:
                period_date = date.fromisoformat(self.snapshot.reference_date)
                days, remaining = business_days(period_date)
                self.footer_left.configure(text=f'Dias úteis: {days}   |   Restantes: {remaining}   |   Falta média: {fmt_cell(stats["gap_average"], "falta", "")}   |   Duplo clique para editar')
            except ValueError:
                self.footer_left.configure(text='Sem data de referência válida')
        else:
            for card in self.kpis:
                card.update_value('—', 'Nenhum dado no período')
            self.source_label.configure(text='Nenhum dado no período. Cadastre pelo F6 ou importe Excel.')
            self.alert_label.configure(text='')
            self.footer_left.configure(text='Aguardando período com dados')
            self.kpis[0].update_value(str(len(filtered)), 'No filtro atual')
            self.kpis[4].update_value(str(len(filtered)), 'Sem atingimento')
        self.overview_panel.update_data(self.snapshot, filtered)
        self.grid_widget.configure_data(self.snapshot, filtered, self._current_rows(),
                                        compact=self.mode_var.get() == 'Telão')
        self.carousel_panel.update_data(self.snapshot, self.visible_areas)
        self.chart_carousel.update_data(self.snapshot, self.visible_areas)
        self.custom_carousel.update_data(self.snapshot, self.visible_areas)
        if self.tabs.select() == str(self.tab_charts):
            self.chart_panel.update_data(self.snapshot, filtered)

    def _tab_changed(self, _event=None):
        self._update_navigation()
        if self.tabs.select() == str(self.tab_charts):
            self.chart_panel.update_data(self.snapshot, self._current_areas())

    def _set_presentation(self, enable, kind=None):
        if enable and kind and kind != self.presentation_kind:
            self._active_carousel().set_active(False)
            self._active_carousel().pack_forget()
            self.presentation_kind = kind
            self._active_carousel().pack(fill='both', expand=True)
            if self.presentation_mode:
                self._active_carousel().set_active(True)
        if enable == self.presentation_mode:
            return
        self.presentation_mode = enable
        if enable:
            self._restore_sidebar = self.sidebar_visible
            if self.sidebar_visible:
                self.toggle_sidebar()
            for widget in (self.topbar, self.kpi_bar, self.toolbar,
                           self.source_line, self.bottom_bar, self.tabs):
                widget.pack_forget()
            self.presentation_view.pack(fill='both', expand=True)
            self._active_carousel().set_active(True)
        else:
            self._active_carousel().set_active(False)
            self.presentation_view.pack_forget()
            self.topbar.pack(fill='x', padx=20, pady=(17, 9))
            self.kpi_bar.pack(fill='x', padx=20, pady=(3, 15))
            self.toolbar.pack(fill='x', padx=20, pady=(0, 8))
            self.source_line.pack(fill='x', padx=23, pady=(0, 5))
            self.tabs.pack(fill='both', expand=True, padx=20, pady=(0, 12))
            self.bottom_bar.pack(side='bottom', fill='x', before=self.tabs)
            if getattr(self, '_restore_sidebar', False) and not self.sidebar_visible:
                self.toggle_sidebar()

    def open_carousel(self):
        self._set_presentation(True, 'cards')

    def open_chart_carousel(self):
        self._set_presentation(True, 'charts')

    def open_custom_carousel(self):
        self.custom_carousel.update_data(self.snapshot, self.visible_areas)
        if not self.custom_carousel.pages:
            return self.open_layout_editor()
        self._set_presentation(True, 'custom')

    def close_carousel(self):
        self._set_presentation(False)

    def toggle_carousel(self):
        self._set_presentation(not self.presentation_mode)

    def open_carousel_settings(self):
        if self.presentation_mode:
            if self.presentation_kind == 'custom':
                return self.open_layout_editor()
            if self.presentation_kind == 'charts':
                return self.chart_carousel.open_settings()
            return self.carousel_panel.show_options()

    def _set_carousel_size(self, event, n):
        if self.presentation_kind == 'custom':
            return
        if self.presentation_mode and event.widget.winfo_toplevel() is self:
            self._active_carousel().set_page_size(n)
            return 'break'

    def _carousel_key(self, event, action):
        if not self.presentation_mode or event.widget.winfo_toplevel() is not self:
            return
        if isinstance(event.widget, (tk.Entry, tk.Text, ttk.Combobox, tk.Button)):
            return
        getattr(self._active_carousel(), action)()
        return 'break'

    def open_area_manager(self):
        was_active = self.presentation_mode
        if was_active:
            self._active_carousel().set_active(False)
        win = AreaManagerDialog(self, self.repo, on_change=self._catalog_changed)
        if was_active:
            win.bind('<Destroy>', lambda e: self._active_carousel().set_active(True)
                     if e.widget is win and self.presentation_mode else None)
        return win

    def _catalog_changed(self, new_key=None):
        self.all_areas = self.repo.list_areas(include_hidden=True)
        self.visible_areas = self.repo.list_areas()
        possible_labels = ['Todas as áreas'] + [a.short for a in self.visible_areas]
        self.area_combo.configure(values=possible_labels)
        if self.area_var.get() not in possible_labels:
            self.area_var.set('Todas as áreas')
        if new_key and self.repo.is_area_visible(new_key):
            # Um novo cartão aparece no carrossel sem precisar alterar checkboxes.
            self.carousel_panel.selected_keys = list(dict.fromkeys(
                self.carousel_panel.selected_keys + [new_key]))
            self.repo.set_setting('carousel_area_selection', self.carousel_panel.selected_keys)
        self._refresh()

    def open_manual_entry(self, area_key=None):
        # Permite edição direta durante a apresentação sem depender do Excel.
        # Quando acionado por atalhos, area_key pode ser um objeto Event.
        if not isinstance(area_key, str):
            area_key = None
        if area_key is None:
            area_key = next((a.key for a in self.visible_areas if a.short == self.area_var.get()), None)
        was_active = self.presentation_mode
        if was_active:
            self._active_carousel().set_active(False)
        current_day = (datetime.strptime(self.day_filter_var.get(), '%d/%m/%Y').date().isoformat()
                       if self.day_filter_var.get() != 'Consolidado' else None)
        if not self.visible_areas:
            messagebox.showwarning('Sem painéis ativos',
                'Ative ou crie um painel em Gerenciar painéis antes de lançar dados.')
            return None
        win = ManualEntryDialog(self, self.repo, self.period_var.get(),
                                area_key, on_save=self._manual_saved,
                                initial_date=current_day)
        if was_active:
            win.bind('<Destroy>', lambda e: self._active_carousel().set_active(True)
                     if e.widget is win and self.presentation_mode else None)
        return win

    def _manual_saved(self, period):
        self.period_combo.configure(values=self.repo.periods())
        if self.period_var.get() != period:
            self.day_filter_var.set(CONSOLIDATED)
        self.period_var.set(period)
        self._refresh()
        self._notify('Dados salvos. Os indicadores já foram atualizados.')

    def _pick_filter_day(self):
        initial = None
        if self.day_filter_var.get() != 'Consolidado':
            try:
                initial = datetime.strptime(self.day_filter_var.get(), '%d/%m/%Y').date().isoformat()
            except ValueError:
                initial = None
        else:
            snap = self.repo.get(self.period_var.get())
            initial = snap.reference_date if snap else None
        chosen = ask_date(self, initial_date=initial, period=self.period_var.get(),
                          title='Selecionar dia do painel', allow_none=True,
                          none_label=CONSOLIDATED)
        if chosen is None:  # Cancelar: não muda o filtro.
            return
        if chosen == CONSOLIDATED:
            self.day_filter_var.set(CONSOLIDATED)
        else:
            new_period = chosen[:7]
            if self.period_var.get() != new_period:
                self.period_var.set(new_period)
                self.period_combo.configure(values=sorted(
                    set(self.repo.periods()) | {new_period}, reverse=True))
            self.day_filter_var.set(datetime.fromisoformat(chosen).strftime('%d/%m/%Y'))
        self._filter_changed()

    def _period_changed(self, _event=None):
        self.day_filter_var.set(CONSOLIDATED)
        self._filter_changed()

    def _filter_changed(self, _event=None):
        if self.mode_var.get() == 'Telão' and self.sidebar_visible:
            self.toggle_sidebar()
        self._refresh()

    def _tick(self):
        if not self.winfo_exists():
            return
        self.clock.configure(text=datetime.now().strftime('%d/%m/%Y  •  %H:%M:%S'))
        self._clock_job = self.after(1000, self._tick)

    def destroy(self):
        if getattr(self, '_notice_job', None):
            self.after_cancel(self._notice_job)
            self._notice_job = None
        if getattr(self, '_clock_job', None):
            try:
                self.after_cancel(self._clock_job)
            except tk.TclError:
                pass
            self._clock_job = None
        super().destroy()

    def _escape(self, _event=None):
        if self.is_fullscreen:
            self.toggle_fullscreen()
        elif self.presentation_mode:
            self.close_carousel()

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side='left', fill='y', before=self.main)
        self.sidebar_visible = not self.sidebar_visible

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)
        if not self.presentation_mode:
            self.mode_var.set('Telão' if self.is_fullscreen else 'Detalhado')
        if self.is_fullscreen and self.sidebar_visible:
            self.toggle_sidebar()
        self._refresh()

    def import_excel(self):
        path = filedialog.askopenfilename(title='Importar aba GERENCIAL',
                                          filetypes=[('Planilhas Excel', '*.xlsx'), ('Todos os arquivos', '*.*')])
        if not path:
            return
        try:
            snap = ExcelGerencialAdapter().import_file(path)
            existing = self.repo.get(snap.period)
            if existing and existing.source.startswith(('MANUAL', 'EDIÇÃO LOCAL')):
                if not messagebox.askyesno('Sobrescrever lançamento manual?',
                    f'O mês {snap.period} contém alterações manuais.\n\n'
                    'Importar o Excel substituirá os dados das áreas originais desse mês. '
                    'Os painéis personalizados serão preservados. Continuar?'):
                    return
            self.repo.replace_month_from_excel(snap)
            self.period_combo.configure(values=self.repo.periods())
            self.period_var.set(snap.period)
            self._refresh()
            nerrors = sum(len(x) for x in snap.errors.values())
            messagebox.showinfo('Excel importado',
                    f'Período: {snap.period}\nÁreas ativas: {len(self.visible_areas)}\n'
                    f'Células de erro: {nerrors}\n\nValores ausentes ficam sem dados, não viram zero.')
        except Exception as exc:
            messagebox.showerror('Erro ao importar planilha', str(exc))

    def refresh_source(self):
        if self.repo.available_days(self.period_var.get()):
            self._refresh()
            self._notify('Dados recarregados. Os lançamentos deste mês estão disponíveis.')
            return
        snap = self.repo.get(self.period_var.get())
        if snap and snap.file_path and Path(snap.file_path).exists():
            try:
                new_snap = ExcelGerencialAdapter().import_file(snap.file_path)
                self.repo.replace_month_from_excel(new_snap)
                self._refresh()
                self._notify('Planilha relida. Os indicadores foram atualizados.')
                return
            except Exception as exc:
                messagebox.showwarning('Atualização', f'Não foi possível reler o Excel: {exc}')
        self._refresh()
        # Não trata SQLite como feed em tempo real.
        self._notify('Dados recarregados deste computador.')

    def export_csv(self):
        if not self.snapshot:
            messagebox.showwarning('Exportar', 'Não há dados disponíveis.')
            return
        path = filedialog.asksaveasfilename(title='Exportar indicadores filtrados',
                  defaultextension='.csv', initialfile=f'PGI_{self.snapshot.period}.csv',
                  filetypes=[('CSV', '*.csv')])
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Período', 'Área', 'Indicador', 'Subcoluna', 'Valor numérico', 'Erro na origem'])
            for area in self._current_areas():
                for metric, title, _ in self._current_rows():
                    for channel, sublabel in [('primary', area.primary), ('secondary', area.secondary)]:
                        if not sublabel:
                            continue
                        v = self.snapshot.areas.get(area.key, {}).get(metric, {}).get(channel)
                        error = self.snapshot.errors.get(area.key, {}).get(metric, '')
                        writer.writerow([self.snapshot.period, area.title, title, sublabel,
                                         '' if v is None else v, error])
        self._notify('Exportação concluída. Arquivo salvo na pasta escolhida.')

    def edit_value(self, area, metric, channel):
        if not self.snapshot:
            return
        win = tk.Toplevel(self)
        win.title('Editar indicador manualmente')
        win.configure(bg=C['surface'])
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        width, height = 480, 250
        win.geometry(f'{width}x{height}+{self.winfo_rootx()+180}+{self.winfo_rooty()+130}')
        sublabel = area.primary if channel == 'primary' else area.secondary
        tk.Label(win, text=area.title, bg=C['surface'], fg=C['text'],
                 font=('Segoe UI', 13, 'bold'), wraplength=435).pack(pady=(19, 5))
        tk.Label(win, text=f'{metric.upper()}  |  {sublabel or "Subcoluna secundária"}',
                 bg=C['surface'], fg=C['muted'], font=('Segoe UI', 10),
                 wraplength=430).pack(pady=(0, 15))
        current = self.snapshot.areas.get(area.key, {}).get(metric, {}).get(channel)
        field = tk.Entry(win, bg=C['surface_3'], fg=C['text'], insertbackground=C['text'],
                         borderwidth=0, font=('Segoe UI', 14), justify='center', width=22)
        if current is not None:
            field.insert(0, str(current * 100 if metric == 'percentual' else current))
        field.pack(ipady=7)
        field.focus_set()
        tk.Label(win, text='Use vírgula ou ponto. Deixe vazio para remover. Percentual: 98 = 98%.',
                 bg=C['surface'], fg=C['muted'], font=('Segoe UI', 9)).pack(pady=7)
        buttons = tk.Frame(win, bg=C['surface'])
        buttons.pack(pady=(6, 14))

        def save():
            raw = field.get().strip().replace('%', '')
            value = number(raw) if raw else None
            if raw and value is None:
                messagebox.showerror('Valor inválido', 'Digite um número válido.', parent=win)
                return
            if metric == 'percentual' and value is not None and abs(value) > 1:
                value /= 100
            if metric == 'percentual' and value is not None and value < 0:
                messagebox.showerror('Percentual inválido', 'O percentual não pode ser negativo.', parent=win)
                return
            if self.day_filter_var.get() != 'Consolidado':
                # Nunca gravar o snapshot parcial de um dia como se fosse o mês inteiro.
                try:
                    raw_text = '' if value is None else str(value * 100 if metric == 'percentual' else value)
                    save_manual_area(self.repo, self.snapshot.period, self.snapshot.reference_date,
                                     area.key, {metric: {channel: raw_text}})
                except Exception as exc:
                    messagebox.showerror('Não foi possível salvar', str(exc), parent=win)
                    return
            else:
                set_value(self.snapshot, area.key, metric, channel, value, area)
                self.snapshot.source = 'EDIÇÃO LOCAL • ' + self.snapshot.source.removeprefix('EDIÇÃO LOCAL • ')
                self.snapshot.file_path = ''
                self.repo.put(self.snapshot)
            win.destroy()
            self._refresh()

        self._button(buttons, 'SALVAR', save, filled=True).pack(side='left', padx=6)
        self._button(buttons, 'CANCELAR', win.destroy).pack(side='left', padx=6)
        win.bind('<Return>', lambda _: save())
        win.bind('<Escape>', lambda _: win.destroy())
