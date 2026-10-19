"""Fluxos de preenchimento e navegação com banco descartável."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from painel.data import SQLiteSnapshotRepository
from painel.manual import save_manual_area


@unittest.skipUnless(os.environ.get('PGI_GUI_TESTS') == '1', 'Requer display ativo.')
class UsabilityGuiTests(unittest.TestCase):
    def setUp(self):
        from painel.app import DashboardApp
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = SQLiteSnapshotRepository(Path(self.tmp.name) / 'test.db')
        self.app = DashboardApp(repository=self.repo)
        self.app.geometry('1366x900')
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def dialog(self):
        from painel.manual import ManualEntryDialog
        dialog = ManualEntryDialog(self.app, self.repo, '2026-11', 'logistica', initial_date='2026-11-02')
        self.app.update()
        return dialog

    def test_simple_mode_saves_destination_and_preserves_other_column(self):
        save_manual_area(self.repo, '2026-11', '2026-11-02', 'logistica', {
            'dia': {'primary': '10'}, 'mes': {'primary': '200', 'secondary': '50'},
            'fcst': {'primary': '400', 'secondary': '100'}})
        dialog = self.dialog()
        self.assertTrue(dialog.fields['mes']['secondary'].winfo_viewable())
        self.assertFalse(dialog.fields['mes']['primary'].winfo_viewable())
        # Alterações via colagem/StringVar também devem marcar como pendente.
        dialog.field_vars['mes']['secondary'].set('75')
        self.assertTrue(dialog._dirty)
        self.assertEqual(dialog.fields['percentual']['secondary'].get(), '75,00')
        self.assertEqual(dialog.fields['percentual']['secondary'].cget('state'), 'readonly')
        with patch('painel.manual.messagebox.showinfo') as popup:
            dialog._save(False)
            popup.assert_not_called()
        values = self.repo.get_day('2026-11-02').areas['logistica']
        self.assertEqual(values['mes'], {'primary': 200., 'secondary': 75.})
        self.assertEqual(values['percentual']['secondary'], .75)
        self.assertFalse(dialog._dirty)
        self.assertIn('salvos', dialog.status_var.get())
        dialog.destroy()

    def test_invalid_number_keeps_database_unchanged_and_identifies_field(self):
        dialog = self.dialog()
        dialog.field_vars['dia']['primary'].set('doze')
        with patch('painel.manual.messagebox.showerror') as popup:
            dialog._save(False)
            popup.assert_not_called()
        self.assertIsNone(self.repo.get_day('2026-11-02'))
        self.assertIn('Valor do dia', dialog.status_var.get())
        self.assertTrue(dialog._dirty)
        dialog.destroy()

    def test_switch_to_advanced_keeps_values_and_saves_modified_hidden_column(self):
        dialog = self.dialog()
        dialog.details_var.set(True)
        dialog._apply_field_layout()
        dialog.field_vars['mes']['primary'].set('123')
        dialog.details_var.set(False)
        dialog._apply_field_layout()
        dialog.field_vars['dia']['primary'].set('4')
        dialog._save(False)
        values = self.repo.get_day('2026-11-02').areas['logistica']
        self.assertEqual(values['mes']['primary'], 123.)
        self.assertEqual(values['dia']['primary'], 4.)
        dialog.destroy()

    def test_save_and_next_keeps_date_and_reports_previous_sector(self):
        dialog = self.dialog()
        dialog.field_vars['dia']['primary'].set('4')
        dialog._save(True)
        self.assertEqual(dialog.area_var.get(), 'TRANSPORTE')
        self.assertEqual(dialog._selected_date(), '2026-11-02')
        self.assertIn('LOGÍSTICA', dialog.status_var.get())
        self.assertEqual(self.repo.get_day('2026-11-02').areas['logistica']['dia']['primary'], 4.)
        self.assertEqual(dialog.fields['dia']['primary'].get(), '')
        dialog.destroy()

    def test_cancel_sector_switch_keeps_unsaved_form(self):
        dialog = self.dialog()
        dialog.field_vars['dia']['primary'].set('4')
        dialog.area_var.set('TRANSPORTE')
        with patch('painel.manual.messagebox.askyesno', return_value=False):
            dialog._selection_changed()
        self.assertEqual(dialog.area_var.get(), 'LOGÍSTICA')
        self.assertEqual(dialog.fields['dia']['primary'].get(), '4')
        self.assertTrue(dialog._dirty)
        dialog.destroy()

    def test_navigation_filter_reset_and_feedback(self):
        self.app.tabs.select(self.app.tab_charts)
        self.app.update()
        self.assertTrue(self.app.charts_nav.selected)
        self.assertFalse(self.app.overview_nav.selected)
        self.app.area_var.set('LOGÍSTICA')
        dialog = self.app.open_manual_entry()
        self.assertEqual(dialog.area_var.get(), 'LOGÍSTICA')
        dialog.destroy()
        self.app._reset_filters()
        self.assertEqual(self.app.area_var.get(), 'Todas as áreas')
        self.assertEqual(self.app.day_filter_var.get(), 'Consolidado')
        with patch('painel.app.messagebox.showinfo') as popup:
            self.app.refresh_source()
            popup.assert_not_called()
        self.assertIn('recarregados', self.app.footer_left.cget('text'))

    def test_save_action_stays_visible_at_minimum_form_size(self):
        dialog = self.dialog()
        dialog.geometry('710x580')
        self.app.update()
        button = dialog.save_button
        self.assertTrue(button.winfo_viewable())
        self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                             dialog.winfo_rooty() + dialog.winfo_height())
        dialog.fields['stk_filho']['primary'].event_generate('<FocusIn>')
        self.app.update()
        self.assertGreater(dialog.canvas.yview()[0], 0)
        dialog.destroy()

    def test_new_day_preserves_monthly_values_not_filled_in(self):
        save_manual_area(self.repo, '2026-11', '2026-11-01', 'logistica', {
            'mes': {'secondary': '50'}, 'fcst': {'secondary': '100'}})
        dialog = self.dialog()
        dialog.field_vars['dia']['primary'].set('0')
        dialog._save(False)
        snap = self.repo.get('2026-11')
        self.assertEqual(snap.areas['logistica']['mes']['secondary'], 50.)
        self.assertEqual(snap.areas['logistica']['fcst']['secondary'], 100.)
        self.assertEqual(snap.areas['logistica']['dia']['primary'], 0.)
        dialog.destroy()

    def test_empty_form_does_not_create_record(self):
        dialog = self.dialog()
        dialog._save(False)
        self.assertIsNone(self.repo.get_day('2026-11-02'))
        self.assertIn('Preencha pelo menos', dialog.status_var.get())
        dialog.destroy()
