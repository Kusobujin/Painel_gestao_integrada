"""Resumo gerencial com leitura explícita de metas e pendências."""
from datetime import datetime
import tkinter as tk

from .config import C
from .metrics import follow_up_areas, fmt_cell, status_of


def display_date(value):
    if not value:
        return 'Não informada'
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime('%d/%m/%Y às %H:%M') if 'T' in value else parsed.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return 'Data inválida'


class OverviewPanel(tk.Frame):
    def __init__(self, parent, on_area):
        super().__init__(parent, bg=C['surface'])
        self.on_area = on_area
        self.canvas = tk.Canvas(self, bg=C['surface'], bd=0, highlightthickness=0)
        from tkinter import ttk
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.content = tk.Frame(self.canvas, bg=C['surface'])
        self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.content)
        self.canvas.bind('<Configure>', self._resize)
        self.content.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.labels = []
        self.canvas.bind('<MouseWheel>', self._scroll)

    def _scroll(self, event):
        if self.content.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def _resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        for label in self.labels:
            label.configure(wraplength=max(180, event.width - 52))

    def _text(self, text, color=None, size=10, bold=False):
        label = tk.Label(self.content, text=text, bg=C['surface'], fg=color or C['muted'],
                         font=('Segoe UI', size, 'bold' if bold else 'normal'),
                         anchor='w', justify='left', wraplength=max(180, self.canvas.winfo_width() - 52))
        label.pack(fill='x', padx=24, pady=(4, 6))
        self.labels.append(label)
        label.bind('<MouseWheel>', self._scroll)

    def update_data(self, snapshot, areas):
        for child in self.content.winfo_children():
            child.destroy()
        self.labels.clear()
        self._text('ACOMPANHAMENTO DA OPERAÇÃO', C['text'], 17, True)
        self._text('Meta cadastrada, sem ajuste pelo avanço do mês. As cores não medem o ritmo diário.')
        if not areas:
            self._text('Nenhuma área ativa neste filtro.', C['warn'], 12)
            return
        if not snapshot:
            self._text('Nenhum lançamento na seleção. Use Lançamento manual ou importe uma planilha.', C['warn'], 12)
            return
        below, missing = follow_up_areas(snapshot, areas)
        self._text('MENORES ATINGIMENTOS', C['text'], 12, True)
        if not below:
            self._text('Nenhuma área com percentual informado abaixo de 95%.' if len(missing) < len(areas)
                       else 'Ainda não há percentuais válidos para comparar.', C['muted'])
        for area, value in below[:3]:
            critical = status_of(value) == 'critico'
            color = C['bad'] if critical else C['warn']
            button = tk.Button(self.content,
                text=f'{area.short}   •   {fmt_cell(value, "percentual", area.key)}   •   {"CRÍTICO" if critical else "ATENÇÃO"}   →',
                command=lambda key=area.key: self.on_area(key),
                bg=C['surface_3'], fg=color, activebackground=C['stroke'], activeforeground=C['text'],
                relief='flat', bd=0, anchor='w', padx=14, pady=8, cursor='hand2',
                font=('Segoe UI', 11, 'bold'), wraplength=650, justify='left')
            button.pack(fill='x', padx=24, pady=3)
            button.bind('<MouseWheel>', self._scroll)
            self.labels.append(button)
        if below:
            self._text('Até três áreas abaixo de 95% • Clique no setor para ver os indicadores.', size=9)
        self._text('PENDÊNCIAS DE INFORMAÇÃO', C['text'], 12, True)
        self._text('Sem atingimento informado: ' + ', '.join(a.short for a in missing) if missing
                   else 'Todas as áreas selecionadas têm atingimento informado.', C['warn'] if missing else C['muted'])
        errors = [a.short for a in areas if snapshot.errors.get(a.key)]
        if errors:
            self._text('Erros registrados na origem: ' + ', '.join(errors), C['bad'])
        tk.Frame(self.content, bg=C['stroke'], height=1).pack(fill='x', padx=24, pady=10)
        self._text('REFERÊNCIA DOS DADOS', C['text'], 12, True)
        self._text(f'Referência: {display_date(snapshot.reference_date)}   |   Registro do conjunto: {display_date(snapshot.imported_at)}')
        self._text(f'Fonte: {snapshot.source}')
        self._text('O consolidado reúne os últimos valores informados por área; as datas podem variar. '
                   'O registro do conjunto não indica a atualização de todos os setores.')
        self._text('COMO LER AS CORES', C['text'], 12, True)    
        self._text('No alvo: ≥ 95% • Atenção: de 80% a menos de 95% • Crítico: < 80%. '
                   'As faixas usam a meta cadastrada, sem ajuste pelo avanço do mês. '
                   'Um acumulado baixo no início do período não comprova atraso. '
                   'O ritmo planejado depende do calendário e da regra de cada indicador.')
        self.canvas.yview_moveto(0)
