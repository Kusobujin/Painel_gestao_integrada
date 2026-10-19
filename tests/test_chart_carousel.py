"""Paginação de gráficos, seleções persistidas e tamanho dos popups."""
import os
import tempfile
import unittest
import time
from unittest.mock import patch
from pathlib import Path

from painel.config import AREAS
from painel.chart_carousel import chart_slides, ChartCarouselPanel
from painel.data import SQLiteSnapshotRepository


class ChartSlideTests(unittest.TestCase):
    def test_absolute_metrics_do_not_mix_area_units(self):
        slides = chart_slides(list(AREAS[:3]), ['Dia'], ['Barras horizontais', 'Colunas'])
        self.assertEqual(len(slides), 6)
        self.assertTrue(all(len(areas) == 1 for _, _, areas in slides))

    def test_status_only_uses_attainment_and_percentages_are_bounded(self):
        slides = chart_slides(list(AREAS), ['Atingimento (%)', 'Falta (%)'],
                              ['Distribuição de status', 'Barras horizontais'])
        self.assertEqual(len(slides), 5)
        self.assertTrue(all(metric == 'Atingimento (%)' for metric, kind, _ in slides if kind == 'Distribuição de status'))
        self.assertTrue(all(len(areas) <= 8 for _, kind, areas in slides if kind != 'Distribuição de status'))

    def test_empty_and_invalid_choices_have_no_slides(self):
        self.assertEqual(chart_slides([], ['Dia'], ['Colunas']), [])
        self.assertEqual(chart_slides(AREAS, ['Dia'], ['Distribuição de status']), [])
        self.assertEqual(chart_slides(AREAS, ['inválido'], ['Colunas']), [])


@unittest.skipUnless(os.environ.get('PGI_GUI_TESTS') == '1', 'Requer display ativo.')
class ChartCarouselGuiTests(unittest.TestCase):
    def setUp(self):
        from painel.app import DashboardApp
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteSnapshotRepository(Path(self.tmp.name) / 'test.db')
        self.app = DashboardApp(repository=self.repo)
        self.app.geometry('1366x900')
        self.app.update()
        self.errors = []
        self.app.report_callback_exception = lambda *args: self.errors.append(args)

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def pump(self, ms=300):
        self.app.after(ms, self.app.quit)
        self.app.mainloop()

    def test_area_chooser_is_complete_with_fullscreen_parent_and_resize(self):
        self.app.open_carousel()
        self.app.toggle_fullscreen()
        win = self.app.carousel_panel.open_area_chooser()
        self.app.update()
        self.assertGreaterEqual(win.winfo_width(), 560)
        self.assertGreaterEqual(win.winfo_height(), 390)
        win.geometry('560x390')
        self.app.update()
        self.assertTrue(win.apply_button.winfo_viewable())
        self.assertLessEqual(win.apply_button.winfo_rooty()+win.apply_button.winfo_height(),
                             win.winfo_rooty()+win.winfo_height())
        win._set_all(False)
        win.vars['linc'].set(True)
        win._apply(self.app.carousel_panel.set_visible_areas)
        self.assertEqual([a.key for a in self.app.carousel_panel.areas], ['linc'])
        self.assertTrue(self.app.carousel_panel.active)
        self.assertFalse(self.errors)

    def test_graphs_pause_navigate_switch_mode_and_return(self):
        self.app.open_chart_carousel()
        panel = self.app.chart_carousel
        self.pump()
        self.assertTrue(panel.active)
        self.assertFalse(self.app.carousel_panel.active)
        self.assertTrue(panel._page_widget.winfo_viewable())
        panel.toggle_play()
        self.assertIsNone(panel._job)
        panel.next()
        self.pump(600)
        self.assertEqual(panel.index, 1)
        panel.previous()
        self.pump(600)
        self.assertEqual(panel.index, 0)
        for count in (1, 2, 3, 4):
            panel.set_page_size(count)
            self.pump()
            self.assertLessEqual(len(panel.pages[0]), count)
            cards = list(panel._page_widget.winfo_children())
            self.assertEqual(len(cards), len(panel.pages[0]))
            self.assertTrue(all(card.plot.plot_canvas is not None for card in cards))
        self.app.open_carousel()
        self.assertFalse(panel.active)
        self.assertTrue(self.app.carousel_panel.active)
        self.app.close_carousel()
        self.app.update()
        self.assertTrue(self.app.tabs.winfo_viewable())
        self.assertFalse(self.errors)

    def test_config_selection_persists_and_excludes_hidden_sectors(self):
        self.app.open_chart_carousel()
        panel = self.app.chart_carousel
        win = panel.open_settings()
        self.app.update()
        self.assertFalse(panel.active)
        for key, var in win.metric_vars.items():
            var.set(key == 'Dia')
        for key, var in win.type_vars.items():
            var.set(key == 'Colunas')
        for key, var in win.area_vars.items():
            var.set(key in ('linc', 'logistica'))
        win.size.set('1 gráfico')
        win.interval.set('30 s')
        win._apply()
        self.assertTrue(panel.active)
        cfg = self.repo.get_setting('chart_carousel')
        self.assertEqual(cfg['metrics'], ['Dia'])
        self.assertEqual(cfg['types'], ['Colunas'])
        self.assertEqual(cfg['interval'], '30 s')
        self.assertEqual(len(panel.pages), 2)
        reopened = ChartCarouselPanel(self.app, repository=self.repo)
        reopened.update_data(self.app.snapshot, self.repo.list_areas())
        self.assertEqual(reopened.pages[0][0][0], 'Dia')
        self.repo.set_area_visible('logistica', False)
        reopened.update_data(self.app.snapshot, self.repo.list_areas())
        self.assertEqual(len(reopened.pages), 1)
        reopened.destroy()
        self.assertFalse(self.errors)

    def test_invalid_status_choice_keeps_configuration_open(self):
        self.app.open_chart_carousel()
        panel = self.app.chart_carousel
        win = panel.open_settings()
        for key, var in win.metric_vars.items():
            var.set(key == 'Dia')
        for key, var in win.type_vars.items():
            var.set(key == 'Distribuição de status')
        win._apply()
        self.assertTrue(win.winfo_exists())
        self.assertIn('Atingimento', win.error.cget('text'))
        win.destroy()
        self.assertTrue(panel.active)
        self.assertFalse(self.errors)

    def test_cached_transition_does_not_redraw_graphs_and_has_no_toolbar(self):
        self.app.open_chart_carousel()
        panel = self.app.chart_carousel
        panel.set_page_size(4)
        self.pump(1700)
        self.assertFalse(any(isinstance(widget, __import__('tkinter').Button)
                             for widget in panel.winfo_children()))
        target = panel._cached_page(1)
        self.pump(700)
        with patch('painel.charts.ChartPanel.render', side_effect=AssertionError('Redesenho durante transição')):
            panel.next()
            self.pump(600)
            self.assertIs(panel._page_widget, target)
            self.assertIsNone(panel._animation_job)
            panel.previous()
            self.pump(600)
            self.assertEqual(panel.index, 0)
        self.assertFalse(self.errors)

    def test_timer_and_rapid_clicks_finish_without_overlapping_transitions(self):
        self.app.open_chart_carousel()
        panel = self.app.chart_carousel
        self.pump(1700)
        panel._stop_timer()
        panel._deadline = time.monotonic() - 1
        panel._tick_timer()
        self.pump(600)
        self.assertEqual(panel.index, 1)
        self.assertIsNone(panel._animation_job)
        self.assertIsNotNone(panel._job)
        panel.toggle_play()
        initial = panel.index
        for _ in range(8):
            panel.next()
        panel.previous()
        self.pump(1800)
        self.assertEqual(panel.index, (initial + 7) % len(panel.pages))
        self.assertIsNone(panel._ready_job)
        self.assertIsNone(panel._animation_job)
        self.assertIsNone(panel._job)
        self.assertLessEqual(len(panel._page_cache), 5)
        self.app.close_carousel()
        self.assertIsNone(panel._warm_job)
        self.assertFalse(self.errors)
