"""Resumo gerencial: faixas, ausência de dados, filtros e navegação."""
import os
import tempfile
import unittest
from pathlib import Path

from painel.config import AREAS, destination_channel
from painel.data import Snapshot, SQLiteSnapshotRepository
from painel.metrics import follow_up_areas, summary


class OverviewLogicTests(unittest.TestCase):
    def setUp(self):
        self.snap = Snapshot('2026-10', '2026-10-13', 'TESTE')
        for area, value in zip(AREAS, (0., .799, .80, .949, .95, 1.2, None)):
            self.snap.areas[area.key] = {'percentual': {destination_channel(area, 'percentual'): value}}

    def test_bands_partition_the_visible_areas(self):
        stats = summary(self.snap, [a.key for a in AREAS], AREAS)
        self.assertEqual((stats['good'], stats['warning'], stats['critical'], stats['missing']), (2, 2, 2, 6))
        self.assertEqual(stats['areas'], stats['good'] + stats['warning'] + stats['critical'] + stats['missing'])
        # Mantém a chave agregada usada por integrações e testes anteriores.
        self.assertEqual(stats['attention'], 4)

    def test_ranking_keeps_zero_and_excludes_unknown_and_unselected(self):
        selected = [AREAS[4], AREAS[2], AREAS[0], AREAS[6]]
        below, missing = follow_up_areas(self.snap, selected)
        self.assertEqual([(a.key, v) for a, v in below], [('linc', 0.), ('transporte', .80)])
        self.assertEqual([a.key for a in missing], ['eui'])

    def test_empty_snapshot_is_missing_not_zero(self):
        below, missing = follow_up_areas(None, AREAS[:2])
        self.assertEqual(below, [])
        self.assertEqual(missing, list(AREAS[:2]))


@unittest.skipUnless(os.environ.get('PGI_GUI_TESTS') == '1', 'Requer display ativo.')
class OverviewGuiTests(unittest.TestCase):
    def setUp(self):
        from painel.app import DashboardApp
        self.tmp = tempfile.TemporaryDirectory()
        self.app = DashboardApp(repository=SQLiteSnapshotRepository(Path(self.tmp.name) / 'test.db'))
        self.app.geometry('1366x768+0+0')
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_initial_overview_drills_down_and_returns_from_carousel(self):
        self.assertEqual(self.app.tabs.select(), str(self.app.tab_overview))
        self.app._open_area_details('embalagem')
        self.assertEqual(self.app.area_var.get(), 'EMBALAGEM')
        self.assertEqual(self.app.kpis[0].value.cget('text'), '1')
        self.assertEqual(self.app.tabs.select(), str(self.app.tab_grid))
        self.app.open_carousel()
        self.app.update()
        self.app.close_carousel()
        self.app.update()
        self.assertEqual(self.app.tabs.select(), str(self.app.tab_grid))
        self.assertTrue(self.app.kpi_bar.winfo_ismapped())

    def test_empty_day_reports_missing_and_clears_ranking(self):
        self.app.day_filter_var.set('01/01/2040')
        self.app._refresh()
        self.app.update()
        self.assertEqual(self.app.kpis[4].value.cget('text'), str(len(self.app.visible_areas)))
        self.assertIn('Nenhum lançamento', ' '.join(label.cget('text') for label in self.app.overview_panel.labels))

    def test_filter_controls_fit_minimum_width(self):
        self.app.geometry('1060x660')
        self.app.update()
        combo = self.app.mode_combo
        self.assertLessEqual(combo.winfo_rootx() + combo.winfo_width(),
                             self.app.winfo_rootx() + self.app.winfo_width())
