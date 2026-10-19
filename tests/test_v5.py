"""V5: catálogo persistente, ocultação global e renomeação não destrutiva."""
from pathlib import Path
import tempfile
import unittest
from painel.data import SQLiteSnapshotRepository, Snapshot
from painel.manual import save_manual_area
from painel.metrics import get_value, summary
from painel.carousel import selected_areas


class AreaCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'painel.db'
        self.repo = SQLiteSnapshotRepository(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_w40_hidden_but_recoverable(self):
        self.assertEqual(len(self.repo.list_areas()), 11)
        self.assertEqual(len(self.repo.list_areas(include_hidden=True)), 12)
        self.assertFalse(self.repo.is_area_visible('garantia'))
        self.assertEqual(self.repo.get_area('garantia').short, 'GARANTIA W40')

    def test_reopen_preserves_all_customizations(self):
        self.repo.rename_area('linc', 'NOVO NOME LINC', 'N LINC', 'Volume', 'Realizado')
        self.repo.set_area_visible('recebimento', False)
        area = self.repo.create_area('QUALIDADE', 'QUALIDADE', 'Previsão', 'Entregue')
        reloaded = SQLiteSnapshotRepository(self.db)
        self.assertEqual(reloaded.get_area('linc').title, 'NOVO NOME LINC')
        self.assertEqual(reloaded.get_area('linc').short, 'N LINC')
        self.assertFalse(reloaded.is_area_visible('recebimento'))
        self.assertTrue(reloaded.is_area_visible(area.key))
        self.assertEqual(len(reloaded.list_areas()), 11)

    def test_new_area_has_stable_key_and_all_metrics(self):
        a = self.repo.create_area('CONTROLE DE QUALIDADE', 'QUALIDADE')
        self.assertTrue(a.key.startswith('custom_'))
        self.assertTrue(a.primary)
        self.assertTrue(a.secondary)
        save_manual_area(self.repo, '2026-10', '2026-10-13', a.key,
                         {'mes': {'secondary': '75'}, 'fcst': {'secondary': '100'},
                          'stk_pai': {'primary': '200'}, 'dia': {'primary': '35'}})
        snap = self.repo.get('2026-10')
        self.assertEqual(get_value(snap,a.key,'mes',a), 75)
        self.assertAlmostEqual(get_value(snap,a.key,'percentual',a), .75)
        self.assertEqual(snap.areas[a.key]['stk_pai']['primary'],200)

    def test_rename_original_preserves_month_and_daily_data(self):
        save_manual_area(self.repo,'2026-10','2026-10-11','linc',{'dia': {'primary':'12'}})
        save_manual_area(self.repo,'2026-10','2026-10-13','linc',{'dia': {'primary':'31'}})
        self.repo.rename_area('linc','ENTRADAS','ENTRADAS','Quantidade prevista','Quantidade final')
        self.assertEqual(get_value(self.repo.get_day('2026-10-11'),'linc','dia',self.repo.get_area('linc')),12)
        self.assertEqual(get_value(self.repo.get('2026-10'),'linc','dia',self.repo.get_area('linc')),31)
        self.assertIn('linc', [a.key for a in self.repo.list_areas()])

    def test_hide_then_restore_keeps_all_history(self):
        new = self.repo.create_area('PINTURA','PINTURA')
        save_manual_area(self.repo,'2026-10','2026-10-13',new.key,{'dia': {'primary': '194'}})
        self.repo.set_area_visible(new.key, False)
        self.assertNotIn(new.key,[a.key for a in self.repo.list_areas()])
        self.assertIn(new.key,self.repo.get('2026-10').areas)
        self.assertIn(new.key,self.repo.get_day('2026-10-13').areas)
        self.repo.set_area_visible(new.key, True)
        self.assertIn(new.key,[a.key for a in self.repo.list_areas()])
        self.assertEqual(self.repo.get_day('2026-10-13').areas[new.key]['dia']['primary'],194)

    def test_hidden_excluded_from_statistics(self):
        save_manual_area(self.repo,'2026-10','2026-10-13','linc',
                         {'mes':{'primary':'90'},'fcst':{'primary':'100'}})
        self.repo.set_area_visible('garantia',True)
        save_manual_area(self.repo,'2026-10','2026-10-13','garantia',
                         {'percentual': {'secondary':'5'}})
        self.repo.set_area_visible('garantia',False)
        visible = self.repo.list_areas()
        stats = summary(self.repo.get('2026-10'), [a.key for a in visible], visible)
        self.assertEqual(stats['known'],1)
        self.assertEqual(stats['areas'],11)
        self.assertEqual(stats['attention'],1)

    def test_hidden_w40_not_in_any_visible_list(self):
        areas = self.repo.list_areas()
        selected = selected_areas(areas, ['garantia','linc'])
        self.assertEqual([a.key for a in selected],['linc'])
        self.assertNotIn('garantia', [x.key for x in areas])

    def test_name_conflicts_are_blocked(self):
        with self.assertRaisesRegex(ValueError,'Já existe'):
            self.repo.create_area('TESTE','LINC')
        new = self.repo.create_area('NOVO','NOVO')
        with self.assertRaisesRegex(ValueError,'Já existe'):
            self.repo.rename_area(new.key, 'NOVO','linc','Meta','Realizado')
        self.assertEqual(self.repo.get_area(new.key).short,'NOVO')

    def test_empty_name_rejected_and_no_data_deleted(self):
        for data in (('', 'TESTE', 'Meta','Real'),('Teste','','Meta','Real'),('Teste','TESTE','','Real')):
            with self.assertRaises(ValueError):
                self.repo.create_area(*data)
        self.assertEqual(len(self.repo.list_areas(include_hidden=True)),12)

    def test_disabled_area_prevents_manual_entry_without_erasing_data(self):
        self.repo.set_area_visible('linc', False)
        with self.assertRaisesRegex(ValueError, 'oculto'):
            save_manual_area(self.repo, '2026-10', '2026-10-13','linc',
                             {'dia': {'primary':'10'}})

    def test_all_data_cleared_keeps_catalog(self):
        a=self.repo.create_area('NOVO','NOVO')
        self.repo.set_area_visible('linc',False)
        self.repo.clear_all_data()
        self.assertFalse(self.repo.is_area_visible('linc'))
        self.assertIsNotNone(self.repo.get_area(a.key))

    def test_excel_reimport_does_not_erase_custom_panel_history(self):
        a = self.repo.create_area('AVARIAS','AVARIAS')
        save_manual_area(self.repo, '2026-10','2026-10-12',a.key,
                         {'dia': {'primary': '19'}})
        save_manual_area(self.repo, '2026-10','2026-10-13','linc',
                         {'dia': {'primary':'23'}})
        incoming = Snapshot(period='2026-10',reference_date='2026-10-05',source='EXCEL',
                            areas={'linc': {'dia': {'primary':7.0}}})
        self.repo.replace_month_from_excel(incoming)
        self.assertEqual(self.repo.get('2026-10').areas[a.key]['dia']['primary'],19)
        self.assertEqual(self.repo.get('2026-10').areas['linc']['dia']['primary'],7)
        self.assertEqual(self.repo.get_day('2026-10-12').areas[a.key]['dia']['primary'],19)
        self.assertIsNone(self.repo.get_day('2026-10-13'))

    def test_renamed_area_clear_by_key_still_works(self):
        a=self.repo.create_area('EXPEDIÇÃO','EXPEDIÇÃO')
        save_manual_area(self.repo, '2026-10','2026-10-13',a.key,{'dia': {'primary':'90'}})
        self.repo.rename_area(a.key,'CARREGAMENTO','CARREGAMENTO','Previsto','Entregue')
        self.repo.clear_area_period('2026-10',a.key)
        self.assertNotIn(a.key,self.repo.get('2026-10').areas)
        self.assertIsNotNone(self.repo.get_area(a.key))


if __name__ == '__main__':
    unittest.main()
