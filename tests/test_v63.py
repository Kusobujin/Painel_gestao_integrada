"""V6.3: calendário navegável e gráficos sem reconstrução de canvas."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from painel.date_picker import CONSOLIDATED, shift_month
from painel.data import SQLiteSnapshotRepository


class CalendarLogicTests(unittest.TestCase):
    def test_month_navigation_crosses_years(self):
        self.assertEqual(shift_month(2026, 10, 1), (2026, 11))
        self.assertEqual(shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(shift_month(2026, 5, -17), (2024, 12))

    def test_month_navigation_year_bounds(self):
        with self.assertRaises(ValueError):
            shift_month(1, 1, -1)
        with self.assertRaises(ValueError):
            shift_month(9999, 12, 1)


@unittest.skipUnless(os.environ.get('PGI_GUI_TESTS') == '1',
                     'Execute os testes visuais com PGI_GUI_TESTS=1 e um display ativo.')
class CalendarChartGuiTests(unittest.TestCase):
    def setUp(self):
        from painel.app import DashboardApp
        self.tmp = tempfile.TemporaryDirectory()
        self.app = DashboardApp(repository=SQLiteSnapshotRepository(Path(self.tmp.name) / 'test.db'))
        self.app.geometry('1450x900+0+0')
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_picker_navigates_without_limiting_competence(self):
        from datetime import date
        from painel.date_picker import DatePickerDialog
        popup = DatePickerDialog(self.app, initial_date='2026-10-13', period='2026-10', allow_none=True)
        self.assertEqual((popup.year, popup.month), (2026, 10))
        popup._shift_month(3)
        self.assertEqual((popup.year, popup.month), (2027, 1))
        popup._select(date(2027, 1, 24))
        popup._confirm()
        self.assertEqual(popup.result, '2027-01-24')

    def test_chart_switches_modes_reusing_canvas(self):
        self.app.tabs.select(self.app.tab_charts)
        self.app.update()
        panel = self.app.chart_panel
        canvas = panel.plot_canvas.get_tk_widget()
        ident = id(canvas)
        for kind in panel.TYPES:
            panel.var_type.set(kind)
            panel.render()
            self.app.update()
            self.assertEqual(id(panel.plot_canvas.get_tk_widget()), ident)
            self.assertEqual(canvas.cget('bg').lower(), '#090a0d')
            self.assertEqual(int(canvas.cget('highlightthickness')), 0)
        self.assertEqual(len(panel.plot_host.winfo_children()), 1)

    def test_filter_calendar_updates_month_and_cancel_preserves_it(self):
        with patch('painel.app.ask_date', return_value='2026-11-07'):
            self.app._pick_filter_day()
        self.assertEqual(self.app.period_var.get(), '2026-11')
        self.assertEqual(self.app.day_filter_var.get(), '07/11/2026')
        with patch('painel.app.ask_date', return_value=None):
            self.app._pick_filter_day()
        self.assertEqual(self.app.period_var.get(), '2026-11')
        self.assertEqual(self.app.day_filter_var.get(), '07/11/2026')
        with patch('painel.app.ask_date', return_value=CONSOLIDATED):
            self.app._pick_filter_day()
        self.assertEqual(self.app.day_filter_var.get(), CONSOLIDATED)

    def test_manual_editor_calendar_updates_period_and_day(self):
        dialog = self.app.open_manual_entry()
        self.assertIsNotNone(dialog)
        with patch('painel.manual.ask_date', return_value='2027-01-31'):
            dialog._pick_day()
        self.assertEqual(dialog.period_var.get(), '2027-01')
        self.assertEqual(dialog.day_var.get(), '31')
        self.assertEqual(dialog._loaded_period, '2027-01')
        self.assertEqual(dialog._loaded_day, '31')
        dialog.destroy()


if __name__ == '__main__':
    unittest.main()
