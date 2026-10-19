"""Grade industrial: headers em dois níveis, rolagem sincronizada, status e edição."""
import tkinter as tk
from tkinter import ttk
import textwrap

from .config import C, ROWS, FCST_LABELS, destination_channel
from .metrics import fmt_cell, status_of


class IndustrialGrid(ttk.Frame):
    HEADER_AREA = 60
    HEADER_DETAIL = 76
    ROW_HEIGHT = 54
    LABEL_WIDTH = 172

    def __init__(self, parent, on_edit=None):
        super().__init__(parent)
        self.on_edit = on_edit
        self.snapshot = None
        self.areas = []
        self.rows = list(ROWS)
        self.compact = False
        self.column_width = 148
        self.left = tk.Canvas(self, width=self.LABEL_WIDTH, bg=C['sidebar'], bd=0, highlightthickness=0)
        self.right = tk.Canvas(self, bg=C['bg'], bd=0, highlightthickness=0)
        self.xbar = ttk.Scrollbar(self, orient='horizontal', command=self.right.xview)
        self.ybar = ttk.Scrollbar(self, orient='vertical', command=self._scroll_y)
        self.left.grid(row=0, column=0, sticky='ns')
        self.right.grid(row=0, column=1, sticky='nsew')
        self.ybar.grid(row=0, column=2, sticky='ns')
        self.xbar.grid(row=1, column=1, sticky='ew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.right.configure(xscrollcommand=self.xbar.set, yscrollcommand=self.ybar.set)
        self.right.bind('<Double-Button-1>', self._double_click)
        for can in (self.left, self.right):
            can.bind('<MouseWheel>', self._mousewheel)
            can.bind('<Button-4>', lambda e: self._scroll_wheel(-1))
            can.bind('<Button-5>', lambda e: self._scroll_wheel(+1))
        self.right.bind('<Shift-MouseWheel>', self._horizontal_wheel)
        self._initial_job = self.after(100, self._initial_draw)

    def destroy(self):
        if getattr(self, '_initial_job', None):
            try:
                self.after_cancel(self._initial_job)
            except tk.TclError:
                pass
            self._initial_job = None
        super().destroy()

    @property
    def header_height(self):
        return self.HEADER_AREA + self.HEADER_DETAIL

    def _initial_draw(self):
        if self.winfo_exists():
            self.draw()

    def configure_data(self, snapshot, areas, rows, compact=False):
        self.snapshot = snapshot
        self.areas = list(areas)
        self.rows = list(rows)
        self.compact = compact
        self.column_width = 139 if compact else 155
        self.right.xview_moveto(0)
        self._scroll_y('moveto', 0)
        self.draw()

    def _scroll_y(self, *args):
        self.right.yview(*args)
        self.left.yview(*args)

    def _scroll_wheel(self, direction):
        self._scroll_y('scroll', direction, 'units')
        return 'break'

    def _mousewheel(self, event):
        units = -1 if event.delta > 0 else 1
        self._scroll_y('scroll', units * 3, 'units')
        return 'break'

    def _horizontal_wheel(self, event):
        self.right.xview_scroll(-3 if event.delta > 0 else 3, 'units')
        return 'break'

    def _column_count(self, area):
        return 1 if self.compact or not area.secondary else 2

    def _area_width(self, area):
        return self.column_width * self._column_count(area)

    def _total_width(self):
        return sum(self._area_width(a) for a in self.areas)

    def _rect(self, can, x1, y1, x2, y2, color, border=None):
        can.create_rectangle(x1, y1, x2, y2, fill=color, outline=border or C['stroke'], width=1)

    def draw(self):
        self.left.delete('all')
        self.right.delete('all')
        total_h = self.header_height + max(1, len(self.rows)) * self.ROW_HEIGHT
        total_w = max(self._total_width(), 10)
        self.left.config(scrollregion=(0, 0, self.LABEL_WIDTH, total_h))
        self.right.config(scrollregion=(0, 0, total_w, total_h))
        self._draw_left(total_h)
        if not self.snapshot or not self.areas:
            self.right.create_text(30, self.header_height + 40, text='Sem dados para o filtro atual.',
                                   anchor='w', fill=C['muted'], font=('Segoe UI', 13))
            return
        x = 0
        for idx, area in enumerate(self.areas):
            self._draw_area(idx, area, x)
            x += self._area_width(area)

    def _draw_left(self, total_h):
        self._rect(self.left, 0, 0, self.LABEL_WIDTH, self.header_height, C['surface_2'])
        self.left.create_text(15, 33, text='MÉTRICAS', font=('Segoe UI', 13, 'bold'),
                              anchor='w', fill=C['text'])
        self.left.create_text(15, 60, text='Controle gerencial', font=('Segoe UI', 10),
                              anchor='w', fill=C['muted'])
        for r, (key, title, description) in enumerate(self.rows):
            y = self.header_height + r * self.ROW_HEIGHT
            bg = C['sidebar'] if r % 2 == 0 else C['stripe']
            self._rect(self.left, 0, y, self.LABEL_WIDTH, y + self.ROW_HEIGHT, bg)
            self.left.create_text(14, y + 17, anchor='w', text=title,
                                  font=('Segoe UI', 10, 'bold'), fill=C['text'])
            self.left.create_text(14, y + 36, anchor='w', text=description,
                                  font=('Segoe UI', 9), fill=C['muted'])

    def _wrapped(self, s, length=19, lines=3):
        wrapped = textwrap.wrap(s, length, break_long_words=False, break_on_hyphens=False)
        return '\n'.join(wrapped[:lines])

    def _draw_area(self, idx, area, x0):
        aw = self._area_width(area)
        header_fill = C['surface_2'] if idx % 2 == 0 else C['surface_3']
        self._rect(self.right, x0, 0, x0 + aw, self.HEADER_AREA, header_fill)
        self.right.create_rectangle(x0, 0, x0 + aw, 3, fill=C['accent'] if idx % 2 == 0 else C['blue'], outline='')
        self.right.create_text(x0 + aw/2, self.HEADER_AREA/2 + 2,
                               text=self._wrapped(area.short if self.compact else area.title, 30, 2),
                               font=('Segoe UI', 11, 'bold'), fill=C['text'], justify='center')
        sublabels = [area.primary] if self.compact or not area.secondary else [area.primary, area.secondary]
        for i, sub in enumerate(sublabels):
            xx = x0 + i * self.column_width
            self._rect(self.right, xx, self.HEADER_AREA,
                       xx + self.column_width, self.header_height, C['surface'])
            self.right.create_text(xx + self.column_width / 2,
                                   self.HEADER_AREA + self.HEADER_DETAIL / 2,
                                   text=self._wrapped(sub, 20 if self.compact else 21, 4),
                                   font=('Segoe UI', 9, 'bold'), justify='center',
                                   fill=C['muted'], width=self.column_width - 14)
        for r, (metric, _title, _description) in enumerate(self.rows):
            y1 = self.header_height + r * self.ROW_HEIGHT
            for subindex in range(self._column_count(area)):
                channel = destination_channel(area, metric) if self.compact else ('primary' if subindex == 0 else 'secondary')
                value = self.snapshot.areas.get(area.key, {}).get(metric, {}).get(channel)
                error = self.snapshot.errors.get(area.key, {}).get(metric)
                # Somente a subcoluna que corresponde ao dado de origem mostra um erro.
                error = error if channel == destination_channel(area, metric) else None
                bg = C['surface'] if r % 2 == 0 else C['stripe']
                fg = C['text'] if value is not None else C['muted']
                if metric == 'percentual' and value is not None:
                    state = status_of(value)
                    bg, fg = {
                        'critico': (C['bad_bg'], C['bad']),
                        'atencao': (C['warn_bg'], C['warn']),
                        'no_alvo': (C['good_bg'], C['good']),
                    }[state]
                elif metric == 'falta' and value is not None and value > 0.05:
                    bg, fg = C['bad_bg'], C['bad']
                xx = x0 + subindex * self.column_width
                self._rect(self.right, xx, y1, xx + self.column_width, y1 + self.ROW_HEIGHT, bg)
                display = 'ERRO' if error else fmt_cell(value, metric, area.key)
                if error:
                    fg = C['bad']
                self.right.create_text(xx + self.column_width / 2, y1 + (21 if metric == 'fcst' and area.key in FCST_LABELS else self.ROW_HEIGHT / 2),
                                       text=display, font=('Segoe UI', 12, 'bold'),
                                       fill=fg, justify='center')
                if metric == 'fcst' and area.key in FCST_LABELS and channel == destination_channel(area, metric):
                    self.right.create_text(xx + self.column_width / 2, y1 + 40,
                                           text=FCST_LABELS[area.key],
                                           font=('Segoe UI', 8, 'bold'), fill=C['muted'])

    def _double_click(self, event):
        if not self.snapshot or not self.on_edit or not self.areas:
            return
        x = self.right.canvasx(event.x)
        y = self.right.canvasy(event.y)
        row_num = int((y - self.header_height) // self.ROW_HEIGHT)
        if y < self.header_height or not 0 <= row_num < len(self.rows):
            return
        metric = self.rows[row_num][0]
        if metric == 'falta':  # sempre calculado
            return
        cursor = 0
        for area in self.areas:
            width = self._area_width(area)
            if cursor <= x < cursor + width:
                subindex = 0 if self.compact else int((x - cursor) // self.column_width)
                channel = destination_channel(area, metric) if self.compact else ('primary' if subindex == 0 else 'secondary')
                self.on_edit(area, metric, channel)
                return
            cursor += width
