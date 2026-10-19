"""Controles compartilhados para ações e feedback da interface."""
import tkinter as tk
from .config import C


class ActionButton(tk.Button):
    def __init__(self, parent, text, command, primary=False, **kwargs):
        self.primary = primary
        self.selected = False
        self.normal_bg = C['accent'] if primary else C['surface_3']
        super().__init__(parent, text=text, command=command, bg=self.normal_bg,
                         fg=C['text'], activebackground=C['blue'] if primary else C['stroke'],
                         activeforeground=C['text'], disabledforeground=C['muted'],
                         relief='flat', bd=0, cursor='hand2', takefocus=True,
                         highlightthickness=1, highlightbackground=self.normal_bg,
                         highlightcolor=C['text'], font=('Segoe UI', 10, 'bold'), **kwargs)
        self.bind('<Enter>', lambda _: self._paint(True))
        self.bind('<Leave>', lambda _: self._paint(False))
        self.bind('<Return>', lambda _: self.invoke())

    def _paint(self, hover=False):
        color = C['accent'] if self.selected else (
            C['blue'] if self.primary and hover else C['stroke'] if hover else self.normal_bg)
        self.configure(bg=color, highlightbackground=color)

    def set_selected(self, selected):
        self.selected = selected
        self._paint()


def dark_menu(parent):
    return tk.Menu(parent, tearoff=False, bg=C['surface_2'], fg=C['text'],
                   activebackground=C['accent'], activeforeground=C['text'],
                   font=('Segoe UI', 10), relief='flat', bd=0)
