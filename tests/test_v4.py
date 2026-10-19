"""Regressões para seleção de setores, histórico diário e limpezas com backup."""
import json
import tempfile
import unittest
from pathlib import Path

from painel.carousel import selected_areas, paginate_areas
from painel.config import AREAS
from painel.data import SQLiteSnapshotRepository, Snapshot
from painel.manual import ManualEntryDialog, save_manual_area
from painel.metrics import get_value


class V4Tests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repo = SQLiteSnapshotRepository(Path(self.folder.name) / 'painel.db')

    def tearDown(self):
        self.folder.cleanup()

    def _save(self, day, area, actual):
        return save_manual_area(self.repo, '2026-10', day, area,
                                {'dia': {'primary': str(actual)}})

    def test_carousel_checkboxes_select_any_combination_in_original_order(self):
        chosen = selected_areas(AREAS, ['garantia', 'linc', 'sensor'])
        self.assertEqual([a.key for a in chosen], ['linc', 'sensor', 'garantia'])
        self.assertEqual(len(paginate_areas(chosen, 2)), 2)
        self.assertEqual(selected_areas(AREAS, []), [])

    def test_preferences_persist_when_repository_reopens(self):
        self.repo.set_setting('carousel_area_selection', ['linc', 'logistica'])
        reloaded = SQLiteSnapshotRepository(self.repo.path)
        self.assertEqual(reloaded.get_setting('carousel_area_selection'), ['linc', 'logistica'])

    def test_daily_history_isolated(self):
        self._save('2026-10-12', 'linc', 10)
        self._save('2026-10-13', 'linc', 25)
        self.assertEqual(get_value(self.repo.get_day('2026-10-12'), 'linc', 'dia'), 10)
        self.assertEqual(get_value(self.repo.get_day('2026-10-13'), 'linc', 'dia'), 25)
        self.assertEqual(get_value(self.repo.get('2026-10'), 'linc', 'dia'), 25)
        self.assertEqual(self.repo.available_days('2026-10'), ['2026-10-13', '2026-10-12'])
        self.assertIsNone(self.repo.get_day('2026-10-11'))

    def test_edit_past_day_does_not_replace_recent_month_view(self):
        self._save('2026-10-12', 'linc', 10)
        self._save('2026-10-13', 'linc', 20)
        self._save('2026-10-12', 'linc', 99)
        self.assertEqual(get_value(self.repo.get_day('2026-10-12'), 'linc', 'dia'), 99)
        self.assertEqual(get_value(self.repo.get('2026-10'), 'linc', 'dia'), 20)

    def test_clearing_day_preserves_other_days_and_areas(self):
        self._save('2026-10-12', 'linc', 10)
        self._save('2026-10-13', 'linc', 20)
        self._save('2026-10-13', 'logistica', 50)
        backup = self.repo.clear_day_area('2026-10-13', 'linc')
        self.assertTrue(backup.exists())
        self.assertEqual(get_value(self.repo.get_day('2026-10-12'), 'linc', 'dia'), 10)
        self.assertEqual(get_value(self.repo.get('2026-10'), 'linc', 'dia'), 10)
        self.assertEqual(get_value(self.repo.get_day('2026-10-13'), 'logistica', 'dia'), 50)

    def test_clearing_area_preserves_remaining_month(self):
        self._save('2026-10-12', 'linc', 10)
        self._save('2026-10-13', 'linc', 20)
        self._save('2026-10-13', 'sensor', 75)
        backup = self.repo.clear_area_period('2026-10', 'linc')
        self.assertTrue(backup.exists())
        self.assertNotIn('linc', self.repo.get('2026-10').areas)
        self.assertEqual(get_value(self.repo.get_day('2026-10-13'), 'sensor', 'dia'), 75)
        self.assertIsNone(self.repo.get_day('2026-10-12'))

    def test_clear_everything_does_not_reset_carousel_preferences_or_seed(self):
        self._save('2026-10-13', 'linc', 55)
        self.repo.set_setting('carousel_area_selection', ['linc'])
        backup = self.repo.clear_all_data()
        self.assertTrue(backup.exists())
        self.assertEqual(self.repo.periods(), [])
        self.assertIsNone(self.repo.get_day('2026-10-13'))
        self.repo.seed_if_empty(Path(__file__).parent.parent / 'data/exemplo_gerencial.json')
        self.assertEqual(self.repo.periods(), [])
        self.assertEqual(self.repo.get_setting('carousel_area_selection'), ['linc'])

    def test_month_attainment_recalculates_across_days_without_changing_history(self):
        save_manual_area(self.repo, '2026-10', '2026-10-11', 'linc',
                         {'mes': {'primary': '100'}, 'fcst': {'primary': '200'}})
        save_manual_area(self.repo, '2026-10', '2026-10-12', 'linc',
                         {'mes': {'primary': '150'}})
        self.assertAlmostEqual(get_value(self.repo.get('2026-10'), 'linc', 'percentual'), .75)
        self.assertAlmostEqual(get_value(self.repo.get_day('2026-10-11'), 'linc', 'percentual'), .50)
        self.assertIsNone(get_value(self.repo.get_day('2026-10-12'), 'linc', 'percentual'))

    def test_day_dropdown_respects_leap_year(self):
        self.assertEqual(len(ManualEntryDialog._days_in_month('2028-02')), 29)
        self.assertEqual(len(ManualEntryDialog._days_in_month('2026-02')), 28)
        self.assertEqual(len(ManualEntryDialog._days_in_month('2026-04')), 30)

    def test_import_resets_old_daily_history(self):
        self._save('2026-10-13', 'linc', 55)
        snap = Snapshot(period='2026-10', reference_date='2026-10-05', source='EXCEL',
                        areas={'linc': {'dia': {'primary': 1.0}}})
        self.repo.replace_month_from_excel(snap)
        self.assertEqual(self.repo.available_days('2026-10'), [])
        self.assertEqual(get_value(self.repo.get('2026-10'), 'linc', 'dia'), 1.0)


if __name__ == '__main__':
    unittest.main()
