"""Visualizações gerenciais dinâmicas embutidas em Tkinter / Matplotlib."""
import tkinter as tk
import textwrap
from tkinter import ttk
from .config import C
from .metrics import fmt_number, get_value, status_of
from .ui import ActionButton


class ChartPanel(tk.Frame):
    TYPES = ('Barras horizontais', 'Colunas', 'Linha comparativa', 'Distribuição de status')
    METRICS = {
        'Atingimento (%)': 'percentual',
        'Falta (%)': 'falta',
        'Dia': 'dia',
        'Cap. / Saldo': 'capacidade',
        'Mês realizado': 'mes',
        'Estoque pai': 'stk_pai',
        'Estoque filho': 'stk_filho',
        'FCST / BBP': 'fcst',
    }

    def __init__(self, parent, presentation=False, on_present=None):
        super().__init__(parent, bg=C['bg'], bd=0, highlightthickness=0)
        self.figure = None
        self.ax = None
        self.var_type = tk.StringVar(value=self.TYPES[0])
        self.var_metric = tk.StringVar(value='Atingimento (%)')
        self.snapshot = None
        self.areas = []
        self.plot_canvas = None
        self._layout_job = None
        self.presentation = presentation
        self.compact = False
        self.header = tk.Frame(self, bg=C['surface'])
        self.header.pack(fill='x', padx=14, pady=(10, 2))
        title_row = tk.Frame(self.header, bg=C['surface'])
        title_row.pack(fill='x')
        tk.Label(title_row, text='Desempenho por área', bg=C['surface'], fg=C['text'],
                 font=('Segoe UI', 15, 'bold')).pack(side='left', padx=12, pady=10)
        if on_present:
            ActionButton(title_row, 'Apresentar gráficos', on_present, primary=True,
                         padx=12, pady=8).pack(side='right', padx=12)
        selectors = tk.Frame(self.header, bg=C['surface'])
        selectors.pack(fill='x', pady=(0, 8))
        type_select = ttk.Combobox(selectors, textvariable=self.var_type, width=24,
                                   values=self.TYPES, state='readonly')
        type_select.pack(side='right', padx=(2, 12))
        type_select.bind('<<ComboboxSelected>>', lambda _: self.render())
        tk.Label(selectors, text='GRÁFICO', bg=C['surface'], fg=C['muted'],
                 font=('Segoe UI', 9, 'bold')).pack(side='right', padx=(9, 2))
        metric_select = ttk.Combobox(selectors, textvariable=self.var_metric, width=19,
                                     values=list(self.METRICS), state='readonly')
        metric_select.pack(side='right', padx=(2, 5))
        metric_select.bind('<<ComboboxSelected>>', self._metric_changed)
        tk.Label(selectors, text='MÉTRICA', bg=C['surface'], fg=C['muted'],
                 font=('Segoe UI', 9, 'bold')).pack(side='right', padx=(9, 2))
        self.plot_host = tk.Frame(self, bg=C['bg'], bd=0, highlightthickness=0)
        self.plot_host.pack(expand=True, fill='both', padx=14, pady=8)
        self.note = tk.Label(self, bg=C['bg'], fg=C['muted'],
                             text='', font=('Segoe UI', 9), wraplength=950, justify='left')
        self.note.pack(side='bottom', anchor='w', padx=24, pady=(0, 10), before=self.plot_host)
        if presentation:
            self.header.pack_forget()
            self.note.configure(font=('Segoe UI', 10), wraplength=650)

    def destroy(self):
        if self._layout_job:
            self.after_cancel(self._layout_job)
            self._layout_job = None
        # Matplotlib pode deixar draw_idle agendado ao fechar a janela.
        if self.plot_canvas is not None:
            widget = self.plot_canvas.get_tk_widget()
            for attr in ('_idle_draw_id', '_event_loop_id'):
                job = getattr(self.plot_canvas, attr, None)
                if job:
                    try:
                        widget.after_cancel(job)
                    except tk.TclError:
                        pass
                    setattr(self.plot_canvas, attr, None)
        super().destroy()

    def _metric_changed(self, _event=None):
        if self.METRICS[self.var_metric.get()] != 'percentual' and self.var_type.get() == 'Distribuição de status':
            self.var_type.set('Barras horizontais')
        self.render()

    def update_data(self, snapshot, areas):
        self.snapshot = snapshot
        self.areas = list(areas)
        self.render()

    def _ensure_canvas(self):
        """Cria o canvas UMA vez. Não destrói widgets durante trocas de gráfico."""
        if self.plot_canvas is not None:
            return True
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            if not getattr(self, '_missing_label', None):
                self._missing_label = tk.Label(self.plot_host, bg=C['bg'], fg=C['warn'],
                    font=('Segoe UI', 12),
                    text='Matplotlib não instalado. Execute: pip install -r requirements.txt')
                self._missing_label.pack(pady=80)
            return False
        width, height = max(300, self.plot_host.winfo_width()), max(180, self.plot_host.winfo_height())
        self.figure = Figure(figsize=(width/95, height/95), dpi=95, facecolor=C['bg'])
        self.figure.patch.set_facecolor(C['bg'])
        self.plot_canvas = FigureCanvasTkAgg(self.figure, master=self.plot_host)
        widget = self.plot_canvas.get_tk_widget()
        widget.configure(bg=C['bg'], highlightthickness=0, borderwidth=0, relief='flat')
        widget.pack(fill='both', expand=True, padx=0, pady=0)
        widget.bind('<Configure>', self._schedule_layout, add='+')
        return True

    def _schedule_layout(self, _event=None):
        if self._layout_job:
            self.after_cancel(self._layout_job)
        self._layout_job = self.after(100, self._relayout)

    def _relayout(self):
        self._layout_job = None
        if self.figure and self.figure.axes:
            self._fit_figure()
            self.plot_canvas.draw_idle()

    def _fit_figure(self):
        if self.presentation:
            kind = self.var_type.get()
            if kind == 'Barras horizontais':
                self.figure.subplots_adjust(left=.28, right=.91, top=.94, bottom=.23 if self.compact else .13)
            elif kind == 'Distribuição de status':
                self.figure.subplots_adjust(left=.15, right=.85, top=.88, bottom=.12)
            else:
                self.figure.subplots_adjust(left=.14, right=.95, top=.91, bottom=.31)
        else:
            self.figure.tight_layout(pad=2.2)

    def render(self):
        if not self._ensure_canvas():
            return
        # Pinta o novo gráfico fora da vista e atualiza a mesma superfície Tk
        # de uma vez: sem frame branco, sem destruir/recriar o widget.
        self.figure.clear()
        self.figure.patch.set_facecolor(C['bg'])
        if not self.snapshot:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor(C['bg'])
            ax.text(.5, .5, 'Nenhum lançamento na seleção.', transform=ax.transAxes,
                    ha='center', va='center', color=C['muted'], fontsize=14)
            ax.set_axis_off()
            self.plot_canvas.draw()
            return
        metric = self.METRICS[self.var_metric.get()]
        is_percent = metric in ('percentual', 'falta')
        pairs = [(a.short, get_value(self.snapshot, a.key, metric, a)) for a in self.areas]
        pairs = [(name, value) for name, value in pairs if value is not None]
        if self.presentation:
            pairs = [(textwrap.fill(name, 18), value) for name, value in pairs]
        if is_percent:
            self.note.configure(text='Percentuais por área, sem ponderação. A linha comparativa NÃO representa uma série histórica temporal.')
        else:
            self.note.configure(text='ATENÇÃO: Áreas possuem unidades e escalas distintas (R$, peças, pessoas etc.). '
                                     'Não some nem compare diretamente valores absolutos incompatíveis; use o filtro ÁREA.')
        fig = self.figure
        ax = fig.add_subplot(111)
        ax.set_facecolor(C['bg'])
        ax.tick_params(colors=C['muted'], labelsize=11 if self.presentation and not self.compact else 9)
        for spine in ax.spines.values():
            spine.set_color(C['stroke'])
        if not pairs:
            ax.text(0.5, 0.5, 'Nenhum valor válido no indicador selecionado.',
                    ha='center', va='center', transform=ax.transAxes, color=C['muted'], fontsize=13)
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            labels, raw_values = zip(*pairs)
            values = [v * 100 if is_percent else v for v in raw_values]
            colors = []
            for v in raw_values:
                if metric == 'percentual':
                    colors.append(C['good'] if v >= 0.95 else C['warn'] if v >= 0.80 else C['bad'])
                elif metric == 'falta':
                    colors.append(C['good'] if v <= 0.05 else C['warn'] if v <= 0.20 else C['bad'])
                else:
                    colors.append(C['blue'])
            mode = self.var_type.get()
            if mode == 'Distribuição de status' and metric == 'percentual':
                statuses = [status_of(v) for v in raw_values]
                counts = [statuses.count(s) for s in ('no_alvo', 'atencao', 'critico')]
                names = ['No alvo (≥95%)', 'Atenção (80–95%)', 'Crítico (<80%)']
                groups = [(c, n, color) for c, n, color in zip(counts, names, (C['good'], C['warn'], C['bad'])) if c]
                ax.pie([c for c, _, _ in groups], labels=[n for _, n, _ in groups],
                       colors=[color for _, _, color in groups], autopct='%1.0f%%',
                       wedgeprops={'width': 0.43, 'edgecolor': C['bg']},
                       textprops={'color': C['text'], 'fontsize': 10})
                ax.set_aspect('equal')
            elif mode == 'Barras horizontais' or mode == 'Distribuição de status':
                bars = ax.barh(list(labels)[::-1], values[::-1], color=colors[::-1])
                if metric == 'percentual':
                    ax.axvline(95, color=C['muted'], linestyle='--', linewidth=1)
                ax.set_xlabel(self.var_metric.get(), color=C['muted'])
                ax.margins(x=0.17)
                for bar in bars:
                    x = bar.get_width()
                    value_text = f'{x:.1f}%'.replace('.', ',') if is_percent else fmt_number(float(x))
                    ax.annotate(value_text, (x, bar.get_y() + bar.get_height()/2),
                                xytext=(5 if x >= 0 else -5, 0), textcoords='offset points',
                                ha='left' if x >= 0 else 'right', va='center',
                                color=C['text'], fontsize=12 if self.presentation and not self.compact else 9)
            elif mode == 'Colunas':
                bars = ax.bar(range(len(values)), values, color=colors, width=0.65)
                ax.set_xticks(range(len(values)), labels, rotation=30, ha='right')
                ax.set_ylabel(self.var_metric.get(), color=C['muted'])
                if metric == 'percentual':
                    ax.axhline(95, color=C['muted'], linestyle='--', linewidth=1)
                ax.margins(y=0.19)
                for bar in bars:
                    value_text = f'{bar.get_height():.1f}%'.replace('.', ',') if is_percent else fmt_number(float(bar.get_height()))
                    ax.annotate(value_text, (bar.get_x() + bar.get_width()/2, bar.get_height()),
                                xytext=(0, 4), textcoords='offset points', ha='center',
                                color=C['text'], fontsize=11 if self.presentation and not self.compact else 8)
            else:
                ax.plot(range(len(values)), values, marker='o', color=C['blue'], linewidth=2)
                ax.set_xticks(range(len(values)), labels, rotation=30, ha='right')
                ax.set_ylabel(self.var_metric.get(), color=C['muted'])
                if metric == 'percentual':
                    ax.axhline(95, color=C['muted'], linestyle='--', linewidth=1)
                ax.grid(alpha=0.16, color=C['muted'])
                if self.presentation:
                    for i, value in enumerate(values):
                        ax.annotate(f'{value:.1f}%'.replace('.', ',') if is_percent else fmt_number(float(value)),
                                    (i, value), xytext=(0, 9), textcoords='offset points', ha='center',
                                    color=C['text'], fontsize=9)
                    ax.margins(y=.2)
        self._fit_figure()
        self.plot_canvas.draw()
