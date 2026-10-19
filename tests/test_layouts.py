"""Editor, persistência e apresentação de páginas com conteúdo misto."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from painel.config import AREAS
from painel.data import SQLiteSnapshotRepository
from painel.layouts import (new_layout,new_item,add_item,move_item,resize_item,duplicate_layout,
                           LayoutStore,validate_layouts)


class LayoutLogicTests(unittest.TestCase):
    def test_grid_swap_resize_and_overlap(self):
        layout=new_layout()
        a=add_item(layout,new_item('chart',AREAS),(0,0))
        b=add_item(layout,new_item('indicator',AREAS),(1,0))
        self.assertIsNone(add_item(layout,new_item('chart',AREAS),(0,0)))
        self.assertTrue(move_item(layout,a['id'],1,0))
        self.assertEqual((b['x'],b['y']),(0,0))
        # Largo pode ir para a linha de baixo, sem mover o outro bloco.
        self.assertTrue(resize_item(layout,a['id'],'Largo'))
        self.assertEqual(a['y'],1)
        self.assertFalse(resize_item(layout,a['id'],'Tela inteira'))
        validate_layouts([layout])

    def test_duplicate_has_independent_ids_and_contents(self):
        layout=new_layout('Reunião')
        add_item(layout,new_item('indicator',AREAS))
        copy=duplicate_layout(layout)
        self.assertNotEqual(layout['id'],copy['id'])
        self.assertNotEqual(layout['items'][0]['id'],copy['items'][0]['id'])
        copy['items'][0]['areas']=['logistica']
        self.assertEqual(layout['items'][0]['areas'],['linc'])

    def test_invalid_or_mixed_units_do_not_save(self):
        layout=new_layout()
        item=add_item(layout,new_item('chart',AREAS))
        item['metric']='Dia'
        with self.assertRaises(ValueError):validate_layouts([layout])
        item['areas']=['linc']
        validate_layouts([layout])
        item['chart']='Distribuição de status'
        with self.assertRaises(ValueError):validate_layouts([layout])

    def test_persistence_order_enabled_and_removal_preserve_presets(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=SQLiteSnapshotRepository(Path(folder)/'test.db')
            repo.set_setting('chart_carousel',{'metrics':['Dia']})
            layouts=[new_layout('Primeiro'),new_layout('Segundo')]
            for layout in layouts:add_item(layout,new_item('indicator',AREAS))
            layouts[0]['enabled']=False
            LayoutStore(repo).save(layouts)
            reopened=LayoutStore(SQLiteSnapshotRepository(repo.path)).load()
            self.assertEqual(reopened,layouts)
            LayoutStore(repo).save([])
            self.assertEqual(repo.get_setting('chart_carousel'),{'metrics':['Dia']})
            self.assertEqual(len(repo.list_areas(include_hidden=True)),12)


@unittest.skipUnless(os.environ.get('PGI_GUI_TESTS')=='1','Requer display ativo.')
class LayoutGuiTests(unittest.TestCase):
    def setUp(self):
        from painel.app import DashboardApp
        self.tmp=tempfile.TemporaryDirectory()
        self.repo=SQLiteSnapshotRepository(Path(self.tmp.name)/'test.db')
        self.app=DashboardApp(repository=self.repo)
        self.app.geometry('1366x900')
        self.app.update()
        self.errors=[]
        self.app.report_callback_exception=lambda *args:self.errors.append(args)

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def pump(self,ms=400):
        self.app.after(ms,self.app.quit)
        self.app.mainloop()

    def test_editor_mix_resize_undo_preview_save_and_present(self):
        editor=self.app.open_layout_editor()
        self.app.update()
        editor._add('chart',(0,0))
        chart=editor._item()
        editor.size_var.set('Largo')
        editor._size_changed()
        self.assertEqual(chart['w'],2)
        editor._add('indicator',(0,1))
        editor._add('indicator',(1,1))
        editor._remove_item()
        self.assertEqual(len(editor._current()['items']),2)
        editor._undo()
        self.assertEqual(len(editor._current()['items']),3)
        preview=editor._preview()
        self.pump()
        self.assertTrue(preview.winfo_exists())
        preview.destroy()
        self.assertTrue(editor._save())
        saved=LayoutStore(self.repo).load()
        self.assertEqual([i['kind'] for i in saved[0]['items']],['chart','indicator','indicator'])
        editor._duplicate()
        editor.seconds_var.set('15 segundos')
        editor._page_properties()
        editor._present()
        self.pump(1400)
        panel=self.app.custom_carousel
        self.assertEqual(self.app.presentation_kind,'custom')
        self.assertEqual(len(panel.pages),2)
        self.assertEqual(panel.interval_seconds,10)
        panel.next()
        self.pump(1000)
        self.assertEqual(panel.interval_seconds,15)
        self.assertTrue(panel._page_widget.winfo_viewable())
        self.app.close_carousel()
        self.assertFalse(panel.active)
        self.assertFalse(self.errors)

    def test_discard_changes_and_delete_layout_keep_operational_data(self):
        editor=self.app.open_layout_editor()
        editor._template()
        self.assertTrue(editor._save())
        original=deepcopy(self.repo.get('2026-10').to_dict())
        editor._duplicate()
        with patch('painel.layout_editor.messagebox.askyesnocancel',return_value=False):editor._close()
        self.assertEqual(len(LayoutStore(self.repo).load()),1)
        editor=self.app.open_layout_editor()
        with patch('painel.layout_editor.messagebox.askyesno',return_value=True):editor._delete_layout()
        self.assertTrue(editor._save())
        editor.destroy()
        self.assertEqual(LayoutStore(self.repo).load(),[])
        self.assertEqual(self.repo.get('2026-10').to_dict(),original)
        self.assertFalse(self.errors)

    def test_hidden_sectors_never_show_old_values(self):
        editor=self.app.open_layout_editor()
        editor._add('chart')
        editor._item()['areas']=['logistica']
        editor._item()['metric']='Dia'
        editor._add('indicator')
        editor._item()['areas']=['logistica']
        editor._save()
        editor.destroy()
        self.repo.set_area_visible('logistica',False)
        self.app._catalog_changed()
        self.app.open_custom_carousel()
        self.pump(700)
        cards=list(self.app.custom_carousel._page_widget.winfo_children())
        self.assertEqual(cards[0].plot.areas,[])
        self.assertEqual(cards[1].value.cget('text'),'—')
        self.assertFalse(self.errors)

    def test_drag_from_library_swap_and_single_sector_selection(self):
        editor=self.app.open_layout_editor()
        editor.geometry('1100x680')
        self.app.update()
        left,top,cw,ch=editor._bounds()
        def event(x,y):
            return SimpleNamespace(x_root=editor.canvas.winfo_rootx()+x,y_root=editor.canvas.winfo_rooty()+y)
        editor._library_start(event(0,0),'chart')
        editor._library_motion(event(left+cw*.5,top+ch*.5))
        editor._library_end(event(left+cw*.5,top+ch*.5))
        chart_id=editor._item()['id']
        editor._add('indicator',(1,0))
        editor.canvas.event_generate('<Motion>',x=int(left+cw*.5),y=int(top+ch*.5))
        editor.canvas.event_generate('<ButtonPress-1>',x=int(left+cw*.5),y=int(top+ch*.5))
        editor.canvas.event_generate('<B1-Motion>',x=int(left+cw*1.5),y=int(top+ch*.5))
        editor.canvas.event_generate('<ButtonRelease-1>',x=int(left+cw*1.5),y=int(top+ch*.5))
        self.assertEqual(next(i for i in editor._current()['items'] if i['id']==chart_id)['x'],1)
        editor.selected_id=next(i['id'] for i in editor._current()['items'] if i['kind']=='indicator')
        editor._load_props()
        editor.area_vars['logistica'].set(True)
        editor._areas_changed('logistica')
        self.assertEqual(editor._item()['areas'],['logistica'])
        self.assertTrue(editor._save())
        editor.destroy()
        self.assertFalse(self.errors)

    def test_disabled_layout_and_preset_modes_stay_separate(self):
        self.repo.set_setting('chart_carousel',{'metrics':['Dia'],'types':['Colunas'],'areas':['linc'],'size':'1 gráfico','interval':'30 s'})
        editor=self.app.open_layout_editor()
        editor._template()
        editor._duplicate()
        editor.enabled_var.set(False)
        editor._page_properties()
        self.assertTrue(editor._save())
        editor.destroy()
        self.app.open_custom_carousel()
        self.pump(500)
        self.assertEqual(len(self.app.custom_carousel.pages),1)
        self.app.open_carousel()
        self.assertEqual(self.app.presentation_kind,'cards')
        self.assertFalse(self.app.custom_carousel.active)
        self.assertEqual(self.repo.get_setting('chart_carousel')['metrics'],['Dia'])
        self.app.open_chart_carousel()
        self.assertEqual(self.app.presentation_kind,'charts')
        self.assertFalse(self.errors)
