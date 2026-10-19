"""Páginas com gráficos e indicadores usando a transição preparada do telão."""
import tkinter as tk

from .chart_carousel import ChartCarouselPanel, ChartCard
from .charts import ChartPanel
from .config import C
from .layouts import LayoutStore
from .metrics import get_value, fmt_cell
from .carousel import status_presentation
from .overview import display_date
from .ui import dark_menu


class IndicatorTile(tk.Frame):
    def __init__(self, parent, item, snapshot, area, on_menu):
        super().__init__(parent, bg=C['surface'], highlightthickness=1, highlightbackground=C['stroke'])
        metric = item['metric']
        self._draw_job = None
        tk.Frame(self, height=4, bg=C['accent']).pack(fill='x')
        title = tk.Label(self, text=area.short if area else 'Setor indisponível', bg=C['surface'], fg=C['text'],
                         font=('Segoe UI', 18, 'bold'), anchor='w', justify='left')
        title.pack(fill='x', padx=20, pady=(14, 6))
        key = 'percentual' if metric == 'Resumo do setor' else ChartPanel.METRICS[metric]
        value = get_value(snapshot, area.key, key, area) if area and snapshot else None
        color = status_presentation(value)[1] if key == 'percentual' else C['text']
        caption=tk.Label(self, text='Atingimento' if metric == 'Resumo do setor' else metric, bg=C['surface'], fg=C['muted'],
                         font=('Segoe UI', 12), anchor='w')
        caption.pack(fill='x', padx=20)
        self.value = tk.Label(self, text=fmt_cell(value, key, area.key if area else ''),
                             bg=C['surface'], fg=color, font=('Segoe UI', 44, 'bold'), anchor='w')
        self.value.pack(fill='x', padx=20, pady=(4, 8))
        badge=None
        if key == 'percentual':
            state, _, bg = status_presentation(value)
            badge=tk.Label(self, text=state, bg=bg, fg=color, font=('Segoe UI', 10, 'bold'), padx=10, pady=5)
            badge.pack(anchor='w', padx=20)
        self.rows = []
        if metric == 'Resumo do setor':
            for row_key, label in (('dia', 'Dia'), ('mes', 'Realizado no mês'), ('fcst', 'Meta do mês')):
                line = tk.Frame(self, bg=C['surface'])
                line.pack(fill='x', padx=20, pady=5)
                label_widget=tk.Label(line, text=label, bg=C['surface'], fg=C['muted'], font=('Segoe UI', 11))
                label_widget.pack(side='left')
                val = get_value(snapshot, area.key, row_key, area) if area and snapshot else None
                val_widget=tk.Label(line, text=fmt_cell(val, row_key, area.key if area else ''), bg=C['surface'],
                                    fg=C['text'], font=('Segoe UI', 14, 'bold'))
                val_widget.pack(side='right')
                self.rows.append((line,label_widget,val_widget))
        if not area:
            tk.Label(self, text='Este setor está oculto ou não existe mais.', bg=C['surface'], fg=C['muted']).pack(padx=20, pady=10)
        def fit(event):
            if event.widget is not self:
                return
            compact=event.height<340
            title.configure(wraplength=max(120,event.width-40),font=('Segoe UI',14 if compact else 18,'bold'))
            caption.configure(font=('Segoe UI',10 if compact else 12))
            self.value.configure(font=('Segoe UI',28 if compact else 44,'bold'))
            self.value.pack_configure(pady=(2,4) if compact else (4,8))
            if badge:
                badge.configure(pady=3 if compact else 5)
            for line,label_widget,val_widget in self.rows:
                line.pack_configure(pady=2 if compact else 5)
                label_widget.configure(font=('Segoe UI',10 if compact else 11))
                val_widget.configure(font=('Segoe UI',12 if compact else 14,'bold'))
        self.bind('<Configure>',fit)
        self._bind_menu(self, on_menu)

    def _bind_menu(self, widget, callback):
        widget.bind('<Button-3>', callback)
        for child in widget.winfo_children():
            self._bind_menu(child, callback)


def build_layout_page(parent, layout, snapshot, areas, on_menu):
    frame = tk.Frame(parent, bg=C['bg'])
    lookup = {a.key: a for a in areas}
    for i in range(2):
        frame.columnconfigure(i, weight=1, uniform='layout_cols')
        frame.rowconfigure(i, weight=1, uniform='layout_rows')
    for item in layout['items']:
        selected = [lookup[key] for key in item['areas'] if key in lookup]
        if item['kind'] == 'chart':
            tile = ChartCard(frame, (item['metric'], item['chart'], selected), snapshot,
                             on_menu, compact=item['h']==1)
        else:
            tile = IndicatorTile(frame, item, snapshot, selected[0] if selected else None, on_menu)
        tile.grid(row=item['y'], column=item['x'], columnspan=item['w'], rowspan=item['h'],
                  sticky='nsew', padx=6, pady=6)
    frame.bind('<Button-3>', on_menu)
    return frame


class CustomCarouselPanel(ChartCarouselPanel):
    def __init__(self, parent, on_editor=None, **kwargs):
        self.on_editor = on_editor
        self.layouts = []
        super().__init__(parent, **kwargs)

    @property
    def interval_seconds(self):
        return self.pages[self.index][0]['seconds'] if self.pages else 10

    def _rebuild(self, keep_index=False):
        self._clear_cache()
        self.layouts = LayoutStore(self.repository).load() if self.repository else []
        self.pages = [[layout] for layout in self.layouts if layout.get('enabled', True)]
        self.index = min(self.index, max(0, len(self.pages)-1)) if keep_index else 0
        if self.active:
            self._render_page()
        self._reset_timer()

    def update_data(self, snapshot, areas):
        self.snapshot, self._all_areas = snapshot, list(areas)
        self._rebuild(keep_index=True)

    def _new_page_widget(self, page):
        return build_layout_page(self.card_host, page[0], self.snapshot, self._all_areas, self.show_options)

    def _render_page(self, animate=False, direction=1):
        if self.pages:
            return super()._render_page(animate,direction)
        self._stop_timer()
        self._clear_cache()
        self.reference_label.configure(text='Layouts personalizados\nNenhuma página ativa')
        label=tk.Label(self.card_host,text='Nenhum layout incluído no carrossel.\n\n'
                       'Botão direito → Editar layouts personalizados',bg=C['bg'],fg=C['muted'],
                       font=('Segoe UI',19),justify='center')
        label._count=1
        label.bind('<Button-3>',self.show_options)
        self._page_widget=label
        self._position(label)
        self._paint_progress()

    @staticmethod
    def _page_ready(frame):
        return all(card._draw_job is None and (not isinstance(card, ChartCard) or
                   (card.plot._layout_job is None and (card.plot.plot_canvas is None or
                    not getattr(card.plot.plot_canvas, '_idle_draw_id', None)))) for card in frame.winfo_children())

    def _wait_for_page(self, index, animate, direction):
        if self.pages:
            self.reference_label.configure(text=f'{self.pages[index][0]["name"]}\nReferência: {display_date(self.snapshot.reference_date) if self.snapshot else "Sem dados"}')
        super()._wait_for_page(index, animate, direction)

    def _persist(self):
        pass  # As definições são salvas exclusivamente pelo editor de layouts.

    def open_settings(self):
        if self.on_editor:
            return self.on_editor()

    def show_options(self, event=None):
        menu = dark_menu(self)
        menu.add_command(label='Editar layouts personalizados…', command=self.open_settings)
        menu.add_separator()
        menu.add_command(label='Pausar' if self.playing else 'Retomar', command=self.toggle_play)
        menu.add_command(label='Anterior', command=self.previous)
        menu.add_command(label='Próxima', command=self.next)
        menu.add_separator()
        menu.add_command(label='Tela cheia / F11', command=self.on_fullscreen)
        menu.add_command(label='Voltar ao painel / F9', command=self.on_exit)
        try:
            menu.tk_popup(event.x_root if event else self.winfo_rootx()+40,
                          event.y_root if event else self.winfo_rooty()+80)
        finally:
            menu.grab_release()
