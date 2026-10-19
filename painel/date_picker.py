"""Calendário compacto, nativo Tkinter, com navegação livre entre meses.

Não depende de tkcalendar e não cria moldura/cabeçalho extra. A janela
nasce oculta para evitar o flash no canto (0,0) do Windows.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
import tkinter as tk

from .config import C

CONSOLIDATED = 'Consolidado'
MONTHS = ('Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
          'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro')
WEEKDAYS = ('SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM')


def shift_month(year, month, delta):
    """Navega mês/ano corretamente, inclusive dezembro ↔ janeiro."""
    total = year * 12 + month - 1 + delta
    y, m = divmod(total, 12)
    if not 1 <= y <= 9999:
        raise ValueError('Ano fora do intervalo permitido.')
    return y, m + 1


class DatePickerDialog(tk.Toplevel):
    def __init__(self, parent, initial_date=None, period=None,
                 title='Selecionar data', allow_none=False,
                 none_label=CONSOLIDATED):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=C['bg'])
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None   # Cancelar nunca altera o filtro.
        self.allow_none = allow_none
        self.none_label = none_label

        try:
            chosen = date.fromisoformat(initial_date) if initial_date else date.today()
        except (TypeError, ValueError):
            chosen = date.today()
        # Competência só define a página inicial; não restringe a navegação.
        if period and (not initial_date or chosen.strftime('%Y-%m') != period):
            try:
                year, month = map(int, period.split('-'))
                chosen = date(year, month, min(chosen.day, calendar.monthrange(year, month)[1]))
            except (TypeError, ValueError):
                pass
        self.selected_date = chosen
        self.year, self.month = chosen.year, chosen.month
        self._build()
        self._draw_days()
        self.bind('<Escape>', lambda _e: self.destroy())
        self.bind('<Return>', lambda _e: self._confirm())
        self.bind('<Left>', lambda _e: self._shift_month(-1))
        self.bind('<Right>', lambda _e: self._shift_month(1))
        self.update_idletasks()
        parent.winfo_toplevel().update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        # Centraliza sobre a janela-mãe (evita parecer um popup deslocado).
        root = parent.winfo_toplevel()
        x = root.winfo_rootx() + (root.winfo_width() - width) // 2
        y = root.winfo_rooty() + (root.winfo_height() - height) // 2
        x = min(max(0, x), max(0, self.winfo_screenwidth() - width))
        y = min(max(0, y), max(0, self.winfo_screenheight() - height))
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.deiconify()
        self.grab_set()
        self.focus_set()

    def _button(self, parent, label, command, *, background=None, foreground=None, width=None):
        return tk.Button(parent, text=label, command=command,
                         bg=background or C['surface_3'], fg=foreground or C['text'],
                         activebackground=C['accent'], activeforeground=C['text'],
                         relief='flat', bd=0, highlightthickness=0, cursor='hand2',
                         font=('Segoe UI', 10, 'bold'), width=width,
                         padx=8, pady=7)

    def _build(self):
        # Único conteúdo: calendário e botões. Sem título redundante na área útil.
        nav = tk.Frame(self, bg=C['bg'])
        nav.pack(fill='x', padx=9, pady=(10, 5))
        self._button(nav, '‹', lambda: self._shift_month(-1), width=3).pack(side='left')
        self.month_label = tk.Label(nav, fg=C['text'], bg=C['bg'], width=23,
                                    font=('Segoe UI Semibold', 13, 'bold'))
        self.month_label.pack(side='left', expand=True)
        self._button(nav, '›', lambda: self._shift_month(1), width=3).pack(side='right')
        body = tk.Frame(self, bg=C['bg'])
        body.pack(padx=10, pady=(0, 5))
        for i, d in enumerate(WEEKDAYS):
            tk.Label(body, text=d, bg=C['bg'], fg=C['muted'], width=5,
                     font=('Segoe UI', 8, 'bold')).grid(row=0, column=i, pady=(1, 3))
        self.day_buttons = []
        for r in range(6):
            line = []
            for c in range(7):
                b = tk.Button(body, bd=0, relief='flat', highlightthickness=0,
                              font=('Segoe UI', 10, 'bold'), width=4, height=1,
                              cursor='hand2', padx=4, pady=8)
                b.grid(row=r + 1, column=c, padx=2, pady=2, sticky='nsew')
                line.append(b)
            self.day_buttons.append(line)
        buttons = tk.Frame(self, bg=C['bg'])
        buttons.pack(fill='x', padx=10, pady=(5, 10))
        if self.allow_none:
            self._button(buttons, self.none_label.upper(), self._set_none).pack(side='left', padx=(0, 4))
        self._button(buttons, 'HOJE', self._set_today).pack(side='left')
        self._button(buttons, 'CANCELAR', self.destroy).pack(side='right')
        self._button(buttons, 'APLICAR', self._confirm, background=C['accent']).pack(side='right', padx=(0, 5))

    def _shift_month(self, delta):
        self.year, self.month = shift_month(self.year, self.month, delta)
        self._draw_days()

    def _draw_days(self):
        self.month_label.configure(text=f'{MONTHS[self.month - 1].upper()}  {self.year}')
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.year, self.month)
        today = date.today()
        for r, row in enumerate(self.day_buttons):
            for c, button in enumerate(row):
                if r >= len(weeks):
                    button.configure(text='', state='disabled', bg=C['bg'])
                    continue
                selected = weeks[r][c]
                current = selected.month == self.month
                bg = (C['accent'] if selected == self.selected_date
                      else C['surface_3'] if selected == today
                      else C['surface'] if current else C['bg'])
                fg = C['text'] if current or selected == self.selected_date else C['muted']
                button.configure(text=str(selected.day), state='normal', bg=bg, fg=fg,
                                 disabledforeground=C['muted'],
                                 command=lambda chosen=selected: self._select(chosen))

    def _select(self, chosen):
        self.selected_date = chosen
        self.year, self.month = chosen.year, chosen.month
        self._draw_days()

    def _set_today(self):
        self._select(date.today())

    def _set_none(self):
        self.result = CONSOLIDATED
        self.destroy()

    def _confirm(self):
        self.result = self.selected_date.isoformat()
        self.destroy()


def ask_date(parent, initial_date=None, period=None, title='Selecionar data',
             allow_none=False, none_label=CONSOLIDATED):
    picker = DatePickerDialog(parent, initial_date=initial_date, period=period,
                              title=title, allow_none=allow_none, none_label=none_label)
    picker.wait_window()
    return picker.result
