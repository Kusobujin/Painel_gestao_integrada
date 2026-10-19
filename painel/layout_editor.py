"""Editor visual de páginas: arrastar blocos, configurar e salvar."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk, messagebox

from .config import C
from .charts import ChartPanel
from .custom_carousel import build_layout_page
from .layouts import (LayoutStore, new_layout, new_item, duplicate_layout, add_item,
                      move_item, resize_item, SIZES, INTERVALS, validate_layouts)
from .metrics import get_value, fmt_cell
from .metrics import status_of
from .ui import ActionButton


class LayoutEditor(tk.Toplevel):
    def __init__(self, parent, repo, snapshot, areas, on_save=None, on_present=None):
        super().__init__(parent)
        self.withdraw()
        self.repo, self.snapshot, self.areas = repo, snapshot, list(areas)
        self.store = LayoutStore(repo)
        self.layouts = self.store.load()
        self.checkpoint = deepcopy(self.layouts)
        self.on_save, self.on_present = on_save, on_present
        self.layout_index = 0
        self.selected_id = None
        self.history = []
        self.loading = False
        self.drag = None
        self.title('Phinia • Montar layouts personalizados')
        self.configure(bg=C['bg'])
        self.transient(parent)
        self.minsize(1100, 680)
        width, height = min(1440, self.winfo_screenwidth()-60), min(880, self.winfo_screenheight()-100)
        self.geometry(f'{width}x{height}+{max(0,(self.winfo_screenwidth()-width)//2)}+{max(0,(self.winfo_screenheight()-height)//2)}')
        self._build()
        if not self.layouts:
            self.layouts.append(new_layout('Meu primeiro layout'))
        self._load_layout()
        self.deiconify()
        self.grab_set()
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.bind('<Escape>', lambda _: self._close())
        self.bind('<Control-s>', lambda _: self._save())
        self.bind('<Control-z>', lambda _: self._undo())

    def _button(self, parent, text, command, primary=False):
        return ActionButton(parent, text, command, primary=primary, padx=10, pady=8)

    def _build(self):
        head = tk.Frame(self, bg=C['bg'])
        head.pack(fill='x', padx=22, pady=(16, 12))
        tk.Label(head, text='Monte sua apresentação', bg=C['bg'], fg=C['text'],
                 font=('Segoe UI', 23, 'bold')).pack(side='left')
        self._button(head, 'Salvar e apresentar', self._present, True).pack(side='right')
        self._button(head, 'Salvar layouts', self._save).pack(side='right', padx=8)
        footer = tk.Frame(self, bg=C['bg'])
        footer.pack(side='bottom', fill='x', padx=22, pady=12)
        self.status = tk.Label(footer, text='', bg=C['bg'], fg=C['muted'], font=('Segoe UI', 10), anchor='w')
        self.status.pack(side='left', fill='x', expand=True)
        self._button(footer, 'Fechar', self._close).pack(side='right')
        body = tk.Frame(self, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=22)
        left_shell = tk.Frame(body, bg=C['surface'], width=215)
        left_shell.pack(side='left', fill='y', padx=(0, 12))
        left_shell.pack_propagate(False)
        left_canvas = tk.Canvas(left_shell, bg=C['surface'], highlightthickness=0)
        left_scroll = ttk.Scrollbar(left_shell, command=left_canvas.yview)
        left_scroll.pack(side='right', fill='y')
        left_canvas.pack(fill='both', expand=True)
        left_canvas.configure(yscrollcommand=left_scroll.set)
        left = tk.Frame(left_canvas, bg=C['surface'])
        left_window = left_canvas.create_window(0, 0, window=left, anchor='nw')
        left_canvas.bind('<Configure>', lambda e: left_canvas.itemconfigure(left_window, width=e.width))
        left.bind('<Configure>', lambda _: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
        self._label(left, 'SUAS PÁGINAS', bold=True)
        self.layout_list = tk.Listbox(left, bg=C['surface_3'], fg=C['text'], selectbackground=C['accent'],
                                     selectforeground=C['text'], relief='flat', bd=0, exportselection=False,
                                     font=('Segoe UI', 11), height=6, activestyle='none')
        self.layout_list.pack(fill='x', padx=12, pady=6)
        self.layout_list.bind('<<ListboxSelect>>', self._choose_layout)
        row = tk.Frame(left, bg=C['surface'])
        row.pack(fill='x', padx=12, pady=3)
        self._button(row, '+ Novo', self._new).pack(side='left')
        self._button(row, 'Duplicar', self._duplicate).pack(side='right')
        row = tk.Frame(left, bg=C['surface'])
        row.pack(fill='x', padx=12, pady=3)
        self._button(row, '↑', lambda: self._reorder(-1)).pack(side='left')
        self._button(row, '↓', lambda: self._reorder(1)).pack(side='left', padx=4)
        self._button(row, 'Excluir', self._delete_layout).pack(side='right')
        tk.Frame(left, height=1, bg=C['stroke']).pack(fill='x', padx=12, pady=14)
        self._label(left, 'ADICIONE UM BLOCO', bold=True)
        self._label(left, 'Clique para adicionar ou arraste para a tela.')
        for kind, label, hint in (('chart', '＋ Gráfico', 'Barras, colunas, linha ou status'),
                                  ('indicator', '＋ Indicador', 'Resumo do setor ou número')):
            library = tk.Label(left, text=label+'\n'+hint, bg=C['surface_3'], fg=C['text'],
                               font=('Segoe UI', 11, 'bold'), justify='left', anchor='w',
                               padx=12, pady=15, wraplength=175, cursor='hand2')
            library.pack(fill='x', padx=12, pady=6)
            library.bind('<Configure>', lambda e: e.widget.configure(wraplength=max(100,e.width-24)))
            library.bind('<ButtonPress-1>', lambda e, k=kind: self._library_start(e, k))
            library.bind('<B1-Motion>', self._library_motion)
            library.bind('<ButtonRelease-1>', self._library_end)
        self._label(left, 'COMECE COM UM MODELO', bold=True)
        self._button(left, 'Gráfico + indicadores', self._template).pack(fill='x', padx=12, pady=6)
        self._label(left, 'Os dois carrosséis prontos continuam disponíveis no menu de apresentação.')

        right = tk.Frame(body, bg=C['surface'], width=265)
        right.pack(side='right', fill='y', padx=(12, 0))
        right.pack_propagate(False)
        self._label(right, 'ESCOLHAS DO BLOCO', bold=True)
        self._label(right, 'Clique em um bloco para ajustar o que aparece.')
        self._button(right, 'Remover bloco selecionado', self._remove_item).pack(side='bottom', fill='x', padx=12, pady=12)
        self.props_canvas = tk.Canvas(right, bg=C['surface'], bd=0, highlightthickness=0)
        scroll = ttk.Scrollbar(right, command=self.props_canvas.yview)
        scroll.pack(side='right', fill='y')
        self.props_canvas.pack(fill='both', expand=True, padx=(12, 0))
        self.props_canvas.configure(yscrollcommand=scroll.set)
        self.props = tk.Frame(self.props_canvas, bg=C['surface'])
        self.props_window = self.props_canvas.create_window(0, 0, window=self.props, anchor='nw')
        self.props_canvas.bind('<Configure>', lambda e: self.props_canvas.itemconfigure(self.props_window, width=e.width))
        self.props.bind('<Configure>', lambda _: self.props_canvas.configure(scrollregion=self.props_canvas.bbox('all')))

        center = tk.Frame(body, bg=C['bg'])
        center.pack(fill='both', expand=True)
        fields = tk.Frame(center, bg=C['surface'])
        fields.pack(fill='x', pady=(0, 12))
        self.name_var = tk.StringVar()
        self.enabled_var = tk.BooleanVar()
        self.seconds_var = tk.StringVar()
        self._label(fields, 'NOME DA PÁGINA')
        tk.Entry(fields, textvariable=self.name_var, bg=C['surface_3'], fg=C['text'],
                 insertbackground=C['text'], relief='flat', font=('Segoe UI', 13)).pack(fill='x', padx=12, ipady=7)
        options = tk.Frame(fields, bg=C['surface'])
        options.pack(fill='x', padx=12, pady=12)
        tk.Checkbutton(options, text='Incluir no carrossel', variable=self.enabled_var,
                       command=self._page_properties, bg=C['surface'], fg=C['text'],
                       selectcolor=C['surface_3'], activeforeground=C['text'], activebackground=C['surface']).pack(side='left')
        seconds = ttk.Combobox(options, textvariable=self.seconds_var, values=[f'{n} segundos' for n in INTERVALS],
                               state='readonly', width=13)
        seconds.pack(side='right')
        seconds.bind('<<ComboboxSelected>>', self._page_properties)
        self.name_var.trace_add('write', lambda *_: self._page_properties())
        tools = tk.Frame(center, bg=C['bg'])
        tools.pack(fill='x', pady=(0, 8))
        self._button(tools, 'Desfazer', self._undo).pack(side='left')
        self._button(tools, 'Ver prévia', self._preview).pack(side='right')
        self.canvas = tk.Canvas(center, bg=C['bg'], highlightthickness=1, highlightbackground=C['stroke'])
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _: self._draw())
        self.canvas.bind('<ButtonPress-1>', self._canvas_start)
        self.canvas.bind('<B1-Motion>', self._canvas_motion)
        self.canvas.bind('<ButtonRelease-1>', self._canvas_end)
        self.canvas.bind('<Delete>', lambda _: self._remove_item())
        tk.Label(center, text='Arraste para organizar; solte sobre outro bloco para trocar.\n'
                 'A prévia rápida mostra a montagem. Ver prévia abre os gráficos completos.', bg=C['bg'], fg=C['muted'],
                 font=('Segoe UI', 10), justify='left', wraplength=550).pack(fill='x', pady=10)

    def _label(self, parent, text, bold=False):
        tk.Label(parent, text=text, bg=parent.cget('bg'), fg=C['text'] if bold else C['muted'],
                 font=('Segoe UI', 10, 'bold' if bold else 'normal'), wraplength=190,
                 justify='left', anchor='w').pack(fill='x', padx=12, pady=(10, 4))

    def _current(self):
        return self.layouts[self.layout_index] if self.layouts else None

    def _item(self):
        layout = self._current()
        return next((i for i in layout['items'] if i['id'] == self.selected_id), None) if layout else None

    def _remember(self):
        self.history.append((deepcopy(self.layouts), self.layout_index, self.selected_id))
        self.history = self.history[-30:]

    def _status(self, text, color=None):
        self.status.configure(text=text, fg=color or C['muted'])

    def _changed(self):
        self._refresh_list()
        self._draw()
        self._status('Alterações não salvas • Ctrl+S para salvar', C['warn'])

    def _refresh_list(self):
        self.layout_list.delete(0, 'end')
        for layout in self.layouts:
            self.layout_list.insert('end', ('● ' if layout['enabled'] else '○ ')+layout['name'])
        if self.layouts:
            self.layout_list.selection_set(self.layout_index)
            self.layout_list.see(self.layout_index)

    def _load_layout(self):
        self.loading = True
        layout = self._current()
        self.name_var.set(layout['name'] if layout else '')
        self.enabled_var.set(layout['enabled'] if layout else False)
        self.seconds_var.set(f'{layout["seconds"]} segundos' if layout else '10 segundos')
        self.loading = False
        self._refresh_list()
        self._load_props()
        self._draw()
        self._status('Arraste um gráfico ou indicador para começar.' if layout and not layout['items'] else
                     'Selecione um bloco para editar. Arraste para organizar.')

    def _choose_layout(self, _event=None):
        selected = self.layout_list.curselection()
        if selected and selected[0] != self.layout_index:
            self.layout_index, self.selected_id = selected[0], None
            self._load_layout()

    def _page_properties(self, _event=None):
        if self.loading or not self._current():
            return
        self._remember()
        self._current().update(name=self.name_var.get(), enabled=self.enabled_var.get(),
                               seconds=int(self.seconds_var.get().split()[0]))
        self._changed()

    def _new(self):
        self._remember()
        self.layouts.append(new_layout(f'Meu layout {len(self.layouts)+1}'))
        self.layout_index, self.selected_id = len(self.layouts)-1, None
        self._load_layout()
        self._changed()

    def _duplicate(self):
        if not self._current():
            return
        self._remember()
        self.layouts.insert(self.layout_index+1, duplicate_layout(self._current()))
        self.layout_index += 1
        self.selected_id = None
        self._load_layout()
        self._changed()

    def _delete_layout(self):
        if not self._current() or not messagebox.askyesno('Excluir layout?',
            f'Remover “{self._current()["name"]}” da apresentação?\nOs dados dos setores continuam salvos.', parent=self):
            return
        self._remember()
        self.layouts.pop(self.layout_index)
        self.layout_index = max(0, min(self.layout_index, len(self.layouts)-1))
        self.selected_id = None
        self._load_layout()
        self._changed()

    def _reorder(self, direction):
        target = self.layout_index+direction
        if 0 <= target < len(self.layouts):
            self._remember()
            self.layouts[self.layout_index], self.layouts[target] = self.layouts[target], self.layouts[self.layout_index]
            self.layout_index = target
            self._load_layout()
            self._changed()

    def _template(self):
        if not self.areas:
            self._status('Cadastre ou ative um setor antes de adicionar blocos.', C['warn'])
            return
        self._remember()
        layout = new_layout('Gráfico + indicadores')
        chart = new_item('chart', self.areas)
        chart.update(w=2)
        add_item(layout, chart, (0, 0))
        for x, area in enumerate(self.areas[:2]):
            add_item(layout, new_item('indicator', [area]), (x, 1))
        if self._current() and not self._current()['items']:
            self.layouts[self.layout_index]=layout
        else:
            self.layouts.append(layout)
            self.layout_index=len(self.layouts)-1
        self.selected_id=chart['id']
        self._load_layout()
        self._changed()

    def _add(self, kind, position=None):
        if not self.areas:
            self._status('Ative um setor para adicionar blocos.', C['warn'])
            return
        if not self._current():
            self._new()
        item = new_item(kind, self.areas)
        previous = deepcopy(self.layouts)
        added = add_item(self._current(), item, position)
        if not added:
            self._status('Esse espaço está ocupado. Mova ou remova um bloco para abrir espaço.', C['warn'])
            return
        self.history.append((previous, self.layout_index, self.selected_id))
        self.selected_id = added['id']
        self._load_props()
        self._changed()

    def _remove_item(self):
        item = self._item()
        if item:
            self._remember()
            self._current()['items'].remove(item)
            self.selected_id = None
            self._load_props()
            self._changed()

    def _undo(self):
        if self.history:
            self.layouts, self.layout_index, self.selected_id = self.history.pop()
            self._load_layout()
            self._changed()
        return 'break'

    def _load_props(self):
        for child in self.props.winfo_children():
            child.destroy()
        item = self._item()
        if not item:
            self._label(self.props, 'Selecione um bloco na tela. Suas opções aparecerão aqui.')
            return
        self._label(self.props, 'GRÁFICO' if item['kind']=='chart' else 'INDICADOR', True)
        self.size_var = tk.StringVar(value=next(name for name, size in SIZES.items() if size==(item['w'], item['h'])))
        self._prop_combo('Tamanho', self.size_var, list(SIZES), self._size_changed)
        self.metric_var = tk.StringVar(value=item['metric'])
        self._prop_combo('O que mostrar', self.metric_var,
                         list(ChartPanel.METRICS) if item['kind']=='chart' else ['Resumo do setor', *ChartPanel.METRICS], self._metric_changed)
        if item['kind']=='chart':
            self.chart_var = tk.StringVar(value=item['chart'])
            self._prop_combo('Formato do gráfico', self.chart_var, list(ChartPanel.TYPES), self._chart_changed)
        self._label(self.props, 'Setores do gráfico' if item['kind']=='chart' else 'Setor do indicador', True)
        self.area_vars = {}
        for area in self.areas:
            var = tk.BooleanVar(value=area.key in item['areas'])
            self.area_vars[area.key] = var
            tk.Checkbutton(self.props, text=area.short, variable=var, bg=C['surface'], fg=C['text'],
                           selectcolor=C['surface_3'], activebackground=C['surface'], activeforeground=C['text'],
                           anchor='w', wraplength=210, justify='left', font=('Segoe UI', 10),
                           command=lambda key=area.key: self._areas_changed(key)).pack(fill='x', pady=3)
        unknown = set(item['areas']) - {a.key for a in self.areas}
        if unknown:
            self._label(self.props, 'Este bloco tem setores ocultos. Escolha setores ativos para exibi-los.')
        for child in self.props.winfo_children():
            child.bind('<MouseWheel>', self._props_wheel)
        self.props_canvas.bind('<MouseWheel>', self._props_wheel)

    def _props_wheel(self, event):
        if self.props.winfo_height() > self.props_canvas.winfo_height():
            self.props_canvas.yview_scroll(-1 if event.delta>0 else 1, 'units')
        return 'break'

    def _prop_combo(self, label, variable, choices, callback):
        self._label(self.props, label)
        combo = ttk.Combobox(self.props, textvariable=variable, values=choices, state='readonly', width=20)
        combo.pack(fill='x', padx=(0, 10), pady=(0, 8))
        combo.bind('<<ComboboxSelected>>', callback)

    def _size_changed(self, _event=None):
        self._remember()
        if not resize_item(self._current(), self.selected_id, self.size_var.get()):
            self.history.pop()
            self._load_props()
            self._status('Não há espaço para esse tamanho. Mova ou remova os blocos ao lado.', C['warn'])
            return
        self._changed()

    def _metric_changed(self, _event=None):
        self._remember()
        item = self._item()
        item['metric'] = self.metric_var.get()
        if item['kind']=='chart':
            if item['metric'] != 'Atingimento (%)' and item['chart']=='Distribuição de status':
                item['chart'] = 'Barras horizontais'
            if ChartPanel.METRICS[item['metric']] not in ('percentual', 'falta'):
                item['areas'] = item['areas'][:1]
        self._load_props()
        self._changed()

    def _chart_changed(self, _event=None):
        self._remember()
        self._item()['chart'] = self.chart_var.get()
        if self.chart_var.get()=='Distribuição de status':
            self._item()['metric'] = 'Atingimento (%)'
        self._load_props()
        self._changed()

    def _areas_changed(self, clicked):
        item = self._item()
        chosen = [key for key, var in self.area_vars.items() if var.get()]
        single = item['kind']=='indicator' or ChartPanel.METRICS[item['metric']] not in ('percentual', 'falta')
        if single and clicked in chosen:
            chosen = [clicked]
        if not chosen or len(chosen)>8:
            self._load_props()
            self._status('Escolha pelo menos um setor e até oito por gráfico.', C['warn'])
            return
        self._remember()
        item['areas'] = chosen
        self._load_props()
        self._changed()

    def _bounds(self):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        usable_w = max(200, width-24)
        usable_h = min(max(150, height-24), usable_w*9/16)
        return 12, max(12, (height-usable_h)/2), usable_w/2, usable_h/2

    def _position(self, x, y):
        left, top, cw, ch = self._bounds()
        if left <= x < left+cw*2 and top <= y < top+ch*2:
            return int((x-left)//cw), int((y-top)//ch)
        return None

    def _draw(self):
        if not hasattr(self, 'canvas'):
            return
        self.canvas.delete('all')
        left, top, cw, ch = self._bounds()
        for y in range(2):
            for x in range(2):
                self.canvas.create_rectangle(left+x*cw+4, top+y*ch+4, left+(x+1)*cw-4, top+(y+1)*ch-4,
                                             fill=C['sidebar'], outline=C['stroke'], dash=(4, 4))
                self.canvas.create_text(left+(x+.5)*cw, top+(y+.5)*ch, text='Solte um bloco aqui',
                                        fill=C['muted'], font=('Segoe UI', 10))
        layout = self._current()
        if not layout:
            return
        lookup = {a.key: a for a in self.areas}
        for item in layout['items']:
            tag = 'block:'+item['id']
            x1,y1 = left+item['x']*cw+4, top+item['y']*ch+4
            x2,y2 = left+(item['x']+item['w'])*cw-4, top+(item['y']+item['h'])*ch-4
            self.canvas.create_rectangle(x1,y1,x2,y2,fill=C['surface_2'],outline=C['accent'] if item['id']==self.selected_id else C['stroke'],
                                         width=3 if item['id']==self.selected_id else 1,tags=tag)
            self.canvas.create_rectangle(x1,y1,x2,y1+4,fill=C['accent'],outline='',tags=tag)
            selected = [lookup[key] for key in item['areas'] if key in lookup]
            title = item['metric'] if item['kind']=='chart' else (selected[0].short if selected else 'Setor oculto')
            self.canvas.create_text(x1+12,y1+18,text=title,anchor='w',fill=C['text'],font=('Segoe UI', 11, 'bold'),width=max(100,x2-x1-24),tags=tag)
            subtitle = item['chart'] if item['kind']=='chart' else item['metric']
            self.canvas.create_text(x1+12,y1+40,text=subtitle,anchor='w',fill=C['muted'],font=('Segoe UI', 9),width=max(100,x2-x1-24),tags=tag)
            key = 'percentual' if item['metric']=='Resumo do setor' else ChartPanel.METRICS[item['metric']]
            pairs = [(a, get_value(self.snapshot, a.key, key, a)) for a in selected] if self.snapshot else []
            pairs = [(a,v) for a,v in pairs if v is not None]
            if item['kind']=='indicator':
                value = pairs[0][1] if pairs else None
                self.canvas.create_text(x1+12,y1+min(90,(y2-y1)*.62),text=fmt_cell(value,key,selected[0].key if selected else ''),
                    fill=C['good'] if key=='percentual' and value is not None and value>=.95 else C['text'],
                    font=('Segoe UI', 26, 'bold'),anchor='w',tags=tag)
            elif pairs:
                maximum = max(1, max(abs(v) for _,v in pairs))
                if item['chart']=='Distribuição de status':
                    counts = [sum(status_of(v)==s for _,v in pairs) for s in ('no_alvo','atencao','critico')]
                    radius=max(15,min((x2-x1-30)/2,(y2-y1-65)/2))
                    cx,cy=(x1+x2)/2,y1+57+radius
                    start=0
                    for count,color in zip(counts,(C['good'],C['warn'],C['bad'])):
                        if count:
                            extent=count/len(pairs)*360
                            self.canvas.create_arc(cx-radius,cy-radius,cx+radius,cy+radius,start=start,extent=extent,
                                                   fill=color,outline=C['surface_2'],tags=tag)
                            start+=extent
                    self.canvas.create_oval(cx-radius*.55,cy-radius*.55,cx+radius*.55,cy+radius*.55,
                                            fill=C['surface_2'],outline='',tags=tag)
                    continue
                if item['chart'] in ('Colunas','Linha comparativa'):
                    visible=pairs[:5]
                    pw,ph=x2-x1-32,max(20,y2-y1-86)
                    points=[]
                    for i,(area,value) in enumerate(visible):
                        px=x1+16+(i+.5)*pw/len(visible)
                        py=y2-23-ph*abs(value)/maximum
                        color=C['good'] if key=='percentual' and value>=.95 else C['accent']
                        if item['chart']=='Colunas':
                            bw=pw/len(visible)*.55
                            self.canvas.create_rectangle(px-bw/2,py,px+bw/2,y2-23,fill=color,outline='',tags=tag)
                        else:
                            points.extend((px,py))
                            self.canvas.create_oval(px-3,py-3,px+3,py+3,fill=C['accent'],outline='',tags=tag)
                        self.canvas.create_text(px,y2-12,text=area.short[:7],fill=C['muted'],font=('Segoe UI',7),tags=tag)
                    if len(points)>2:
                        self.canvas.create_line(*points,fill=C['accent'],width=2,tags=tag)
                    continue
                row_h = max(10, min(20, (y2-y1-66)/min(5,len(pairs))))
                for i,(area,value) in enumerate(pairs[:5]):
                    py = y1+60+i*row_h
                    self.canvas.create_text(x1+12,py,text=area.short[:13],fill=C['muted'],font=('Segoe UI', 8),anchor='w',tags=tag)
                    bx=x1+min(110,(x2-x1)*.4)
                    self.canvas.create_rectangle(bx,py-4,bx+max(1,(x2-bx-12)*abs(value)/maximum),py+4,
                        fill=C['good'] if key=='percentual' and value>=.95 else C['accent'],outline='',tags=tag)
            else:
                self.canvas.create_text((x1+x2)/2,(y1+y2)/2+20,text='Sem dados na seleção',fill=C['muted'],tags=tag)

    def _canvas_start(self, event):
        self.canvas.focus_set()
        hit = self.canvas.find_withtag('current')
        tags = self.canvas.gettags(hit[0]) if hit else ()
        tag = next((t for t in tags if t.startswith('block:')), None)
        self.selected_id = tag[6:] if tag else None
        self.drag = {'id': self.selected_id} if tag else None
        self._load_props()
        self._draw()

    def _ghost(self, x, y):
        self.canvas.delete('ghost')
        position = self._position(x,y)
        if position:
            left,top,cw,ch=self._bounds()
            px,py=position
            self.canvas.create_rectangle(left+px*cw+4,top+py*ch+4,left+(px+1)*cw-4,top+(py+1)*ch-4,
                                         outline=C['accent'],width=4,dash=(6,4),tags='ghost')

    def _canvas_motion(self,event):
        if self.drag:
            self._ghost(event.x,event.y)

    def _canvas_end(self,event):
        if self.drag and self.drag.get('id') and self._position(event.x,event.y):
            self._remember()
            if move_item(self._current(),self.drag['id'],*self._position(event.x,event.y)):
                self._changed()
            else:
                self.history.pop()
                self._status('Espaço ocupado ou pequeno. Mova o bloco ao lado ou escolha outro tamanho.',C['warn'])
        self.drag=None
        self.canvas.delete('ghost')

    def _library_start(self,event,kind):
        self.drag={'kind':kind,'start':(event.x_root,event.y_root)}

    def _library_motion(self,event):
        self._ghost(event.x_root-self.canvas.winfo_rootx(),event.y_root-self.canvas.winfo_rooty())

    def _library_end(self,event):
        drag,self.drag=self.drag,None
        self.canvas.delete('ghost')
        if drag:
            pos=self._position(event.x_root-self.canvas.winfo_rootx(),event.y_root-self.canvas.winfo_rooty())
            if pos or abs(event.x_root-drag['start'][0])+abs(event.y_root-drag['start'][1])<10:
                self._add(drag['kind'],pos)

    def _save(self):
        try:
            self.store.save(self.layouts)
        except ValueError as exc:
            self._status(str(exc),C['warn'])
            return False
        self.checkpoint=deepcopy(self.layouts)
        if self.on_save:
            self.on_save()
        self._status('Layouts salvos. Sua apresentação está pronta.',C['good'])
        return True

    def _present(self):
        if not any(layout['enabled'] for layout in self.layouts):
            self._status('Marque Incluir no carrossel em pelo menos uma página.',C['warn'])
            return
        if self._save():
            self.destroy()
            if self.on_present:
                self.on_present()

    def _preview(self):
        layout=self._current()
        if not layout or not layout['items']:
            self._status('Adicione um bloco antes de abrir a prévia.',C['warn'])
            return
        win=tk.Toplevel(self)
        win.title('Prévia • '+layout['name'])
        win.configure(bg=C['bg'])
        win.geometry('1000x680')
        win.minsize(760,540)
        win.transient(self)
        self._button(win,'Voltar ao editor',win.destroy).pack(side='bottom',pady=10)
        page=build_layout_page(win,layout,self.snapshot,self.areas,lambda _=None: None)
        page.pack(fill='both',expand=True,padx=10,pady=10)
        win.grab_set()
        win.bind('<Escape>',lambda _:win.destroy())
        win.bind('<Destroy>',lambda e:self.grab_set() if e.widget is win and self.winfo_exists() else None)
        return win

    def _close(self):
        if self.layouts!=self.checkpoint:
            answer=messagebox.askyesnocancel('Salvar layouts?', 'Salvar as alterações antes de fechar?',parent=self)
            if answer is None or (answer and not self._save()):
                return
        self.destroy()
