"""Gerenciador de painéis: cadastro sem exclusão destrutiva de históricos."""
import tkinter as tk
from tkinter import messagebox, ttk

from .config import C


class AreaDetailsDialog(tk.Toplevel):
    """Cria ou edita nomes e cabeçalhos de um painel existente."""
    def __init__(self, parent, area=None, on_save=None):
        super().__init__(parent)
        self.area = area
        self.on_save = on_save
        self.title('PGI • ' + ('Editar painel' if area else 'Criar painel'))
        self.configure(bg=C['bg'])
        self.geometry('615x420')
        self.minsize(560, 400)
        self.transient(parent)
        self.grab_set()
        self.vars = {
            'title': tk.StringVar(value=area.title if area else ''),
            'short': tk.StringVar(value=area.short if area else ''),
            'primary': tk.StringVar(value=area.primary if area else 'Previsto / Produção (Qtd)'),
            'secondary': tk.StringVar(value=area.secondary if area else 'Realizado (Qtd)'),
        }
        tk.Label(self, text='EDITAR PAINEL' if area else 'NOVO PAINEL',
                 bg=C['bg'], fg=C['text'], font=('Segoe UI Semibold', 20, 'bold')).pack(
                     anchor='w', padx=25, pady=(19, 4))
        tk.Label(self, text='A alteração dos nomes não modifica os indicadores nem os dados históricos.',
                 bg=C['bg'], fg=C['muted'], font=('Segoe UI', 10)).pack(anchor='w', padx=25, pady=(0, 15))
        frame = tk.Frame(self, bg=C['surface'], highlightbackground=C['stroke'], highlightthickness=1)
        frame.pack(fill='x', padx=25)
        self.entries = {}
        for i, (key, caption) in enumerate((('title', 'NOME COMPLETO / CABEÇALHO'),
                                            ('short', 'NOME CURTO / CARTÃO DO CARROSSEL'),
                                            ('primary', 'INDICADOR PRINCIPAL'),
                                            ('secondary', 'INDICADOR SECUNDÁRIO (PODE FICAR VAZIO)'))):
            tk.Label(frame, text=caption, bg=C['surface'], fg=C['muted'],
                     font=('Segoe UI', 9, 'bold')).grid(row=i*2, column=0, sticky='w', padx=15,
                                                      pady=(11 if i else 13, 2))
            e = tk.Entry(frame, textvariable=self.vars[key], bg=C['surface_3'], fg=C['text'],
                         insertbackground=C['text'], relief='flat', font=('Segoe UI', 11))
            e.grid(row=i*2+1, column=0, sticky='ew', padx=15, ipady=5, pady=(0, 1))
            self.entries[key] = e
        frame.columnconfigure(0, weight=1)
        bottom = tk.Frame(self, bg=C['bg'])
        bottom.pack(fill='x', padx=25, pady=17)
        tk.Button(bottom, text='SALVAR PAINEL', command=self._save, bg=C['accent'], fg=C['text'],
                  font=('Segoe UI', 10, 'bold'), bd=0, padx=22, pady=10).pack(side='left')
        tk.Button(bottom, text='CANCELAR', command=self.destroy, bg=C['surface_3'],
                  fg=C['text'], bd=0, padx=22, pady=10).pack(side='right')
        self.entries['title'].focus_set()
        self.bind('<Return>', lambda e: self._save())
        self.bind('<Escape>', lambda e: self.destroy())

    def _save(self):
        try:
            key = self.on_save(**{k: v.get() for k, v in self.vars.items()})
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror('Dados inválidos', str(exc), parent=self)
            return
        self.result = key
        self.destroy()


class AreaManagerDialog(tk.Toplevel):
    """Lista painéis ativos e ocultos. Ocultar nunca apaga lançamentos."""
    def __init__(self, parent, repo, on_change):
        super().__init__(parent)
        self.repo = repo
        self.on_change = on_change
        self.title('PGI • Gerenciar painéis')
        self.configure(bg=C['bg'])
        self.geometry('900x630')
        self.minsize(735, 480)
        self.transient(parent)
        self.grab_set()

        head = tk.Frame(self, bg=C['bg'])
        head.pack(fill='x', padx=25, pady=(23, 13))
        tk.Label(head, text='GERENCIAR PAINÉIS', bg=C['bg'], fg=C['text'],
                 font=('Segoe UI Semibold', 22, 'bold')).pack(anchor='w')
        tk.Label(head, text='Crie novos painéis, renomeie qualquer setor ou oculte/restaure sem apagar dados.',
                 bg=C['bg'], fg=C['muted'], font=('Segoe UI', 10)).pack(anchor='w', pady=(5, 0))

        self.info = tk.Label(head, text='', fg=C['muted'], bg=C['bg'],
                             font=('Segoe UI', 10), anchor='w')
        self.info.pack(fill='x', pady=(7, 0))
        frame = tk.Frame(self, bg=C['surface'], highlightbackground=C['stroke'], highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=25, pady=(0, 10))
        style = ttk.Style(self)
        style.configure('Areas.Treeview', background=C['surface'], foreground=C['text'],
                        fieldbackground=C['surface'], rowheight=38, borderwidth=0,
                        font=('Segoe UI', 10))
        style.configure('Areas.Treeview.Heading', background=C['surface_3'], foreground=C['text'],
                        font=('Segoe UI', 10, 'bold'), padding=(9, 10))
        style.map('Areas.Treeview', background=[('selected', C['accent'])],
                  foreground=[('selected', C['text'])])
        self.tree = ttk.Treeview(frame, columns=('status', 'title', 'short', 'main'),
                                 show='headings', selectmode='browse', style='Areas.Treeview')
        for col, heading, width in (('status', 'SITUAÇÃO', 115), ('title', 'NOME COMPLETO', 260),
                                    ('short', 'NOME CURTO', 160), ('main', 'INDICADOR PRINCIPAL', 225)):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, stretch=(col != 'status'), minwidth=85)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True, padx=6, pady=6)
        self.tree.bind('<<TreeviewSelect>>', lambda e: self._update_actions())
        self.tree.bind('<Double-1>', lambda e: self._edit())
        self.tree.tag_configure('hidden', foreground=C['muted'])
        self.entries = {}
        self._reload()

        toolbar = tk.Frame(self, bg=C['bg'])
        toolbar.pack(fill='x', padx=25, pady=(2, 10))
        self._button(toolbar, '+ CRIAR PAINEL', self._create, primary=True).pack(side='left', padx=(0, 8))
        self.btn_edit = self._button(toolbar, 'RENOMEAR / EDITAR', self._edit)
        self.btn_edit.pack(side='left', padx=(0, 8))
        self.btn_visibility = self._button(toolbar, 'OCULTAR PAINEL', self._toggle)
        self.btn_visibility.pack(side='left')
        self._button(toolbar, 'FECHAR', self.destroy).pack(side='right')

        self._update_actions()
        self.bind('<Escape>', lambda e: self.destroy())

    @staticmethod
    def _button(parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, borderwidth=0,
                         bg=C['accent'] if primary else C['surface_3'], fg=C['text'],
                         activebackground=C['accent'], activeforeground=C['text'],
                         font=('Segoe UI', 10, 'bold'), padx=14, pady=11, cursor='hand2')

    def _reload(self, key=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.entries = {entry['area'].key: entry for entry in self.repo.list_area_entries()}
        active = 0
        for k, entry in self.entries.items():
            a, visible = entry['area'], entry['visible']
            active += visible
            self.tree.insert('', 'end', iid=k, values=(
                '● ATIVO' if visible else '○ OCULTO', a.title, a.short, a.primary),
                tags=() if visible else ('hidden',))
        if key and key in self.entries:
            self.tree.selection_set(key)
            self.tree.see(key)
        self._count_text = f'{active} ativos  •  {len(self.entries)-active} ocultos  •  {len(self.entries)} cadastrados'
        if hasattr(self, 'btn_edit'):
            self._update_actions()

    def _chosen(self):
        selected = self.tree.selection()
        return self.entries.get(selected[0]) if selected else None

    def _update_actions(self):
        entry = self._chosen()
        state = 'normal' if entry else 'disabled'
        self.btn_edit.config(state=state)
        self.btn_visibility.config(state=state, text='OCULTAR PAINEL' if not entry or entry['visible']
                                   else 'RESTAURAR PAINEL')
        self.info.config(text=self._count_text + '  •  Ocultar preserva TODOS os dados e o histórico.')

    def _create(self):
        def callback(**fields):
            area = self.repo.create_area(**fields)
            self._reload(area.key)
            self.on_change(new_key=area.key)
            return area.key
        AreaDetailsDialog(self, on_save=callback)

    def _edit(self):
        entry = self._chosen()
        if not entry:
            return
        area = entry['area']
        def callback(**fields):
            self.repo.rename_area(area.key, **fields)
            self._reload(area.key)
            self.on_change()
            return area.key
        AreaDetailsDialog(self, area=area, on_save=callback)

    def _toggle(self):
        entry = self._chosen()
        if not entry:
            return
        area, active = entry['area'], entry['visible']
        verb = 'ocultar' if active else 'restaurar'
        if not messagebox.askyesno(('Ocultar' if active else 'Restaurar') + ' painel?',
                f'Deseja {verb} “{area.short}”?\n\n' +
                ('Ele deixará de aparecer na tabela, gráficos, filtros, editor e carrossel.\n'
                 'Nenhum lançamento será apagado.' if active else
                 'Ele voltará a aparecer no sistema, com o histórico preservado.'), parent=self):
            return
        self.repo.set_area_visible(area.key, not active)
        self._reload(area.key)
        self.on_change()
