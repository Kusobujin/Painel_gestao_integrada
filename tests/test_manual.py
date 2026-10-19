"""Testes de entrada manual: locale PT-BR, preservação de dados e cálculo."""
import json
import tempfile
import unittest
from pathlib import Path

from painel.data import Snapshot, SQLiteSnapshotRepository
from painel.manual import parse_manual_number, save_manual_area
from painel.metrics import get_value

ROOT = Path(__file__).resolve().parent.parent


class ManualTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteSnapshotRepository(Path(self.temp.name) / 'mock.db')

    def tearDown(self):
        self.temp.cleanup()

    def test_numeric_pt_br(self):
        self.assertEqual(parse_manual_number('42.000'), 42000)
        self.assertEqual(parse_manual_number('42.000,50'), 42000.5)
        self.assertEqual(parse_manual_number('123.75'), 123.75)
        self.assertEqual(parse_manual_number('0,020'), .02)
        self.assertAlmostEqual(parse_manual_number('20,3%', True), .203)
        self.assertAlmostEqual(parse_manual_number('1', True), .01)
        self.assertIsNone(parse_manual_number(''))
        for value in ('abc', 'NaN', 'infinity', '12,1,2'):
            with self.assertRaises(ValueError):
                parse_manual_number(value)

    def test_new_month_and_status(self):
        snap = save_manual_area(self.repo, '2026-11', '2026-11-13', 'recebimento', {
            'dia': {'primary': '42.000'},
            'mes': {'secondary': '120000'},
            'fcst': {'secondary': '150000'},
        })
        self.assertEqual(snap.period, '2026-11')
        self.assertEqual(get_value(snap, 'recebimento', 'dia'), 42000)
        self.assertAlmostEqual(get_value(snap, 'recebimento', 'percentual'), .8)
        self.assertAlmostEqual(get_value(snap, 'recebimento', 'falta'), .2)
        self.assertFalse(snap.file_path)
        self.assertIn('MANUAL', snap.source)
        self.assertEqual(self.repo.periods(), ['2026-11'])

    def test_keeps_other_areas_and_removes_excel_link(self):
        snap = Snapshot.from_dict(json.loads((ROOT / 'data' / 'exemplo_gerencial.json').read_text(encoding='utf-8')))
        snap.file_path = 'origem.xlsx'
        self.repo.put(snap)
        old = get_value(snap, 'recebimento', 'mes')
        new = save_manual_area(self.repo, '2026-10', '2026-10-13', 'logistica', {
            'mes': {'secondary': '99'}, 'fcst': {'secondary': '100'}
        })
        self.assertEqual(get_value(new, 'recebimento', 'mes'), old)
        self.assertAlmostEqual(get_value(new, 'logistica', 'percentual'), .99)
        self.assertFalse(new.file_path)
        self.assertIn('MANUAL', new.source)

    def test_manually_enter_percent_when_no_forecast(self):
        snap = save_manual_area(self.repo, '2026-11', '2026-11-01', 'sensor', {
            'percentual': {'secondary': '97,5'},
        })
        self.assertAlmostEqual(get_value(snap, 'sensor', 'percentual'), .975)
        self.assertAlmostEqual(get_value(snap, 'sensor', 'falta'), .025)

    def test_validation_and_unchanged_database_on_failure(self):
        for month, day in [('2026-13', '2026-10-01'), ('2026-10', '2026-11-01')]:
            with self.assertRaises(ValueError):
                save_manual_area(self.repo, month, day, 'linc', {'dia': {'primary': '25'}})
        with self.assertRaises(ValueError):
            save_manual_area(self.repo, '2026-11', '2026-11-01', 'linc', {'dia': {'primary': 'texto'}})
        self.assertEqual(self.repo.periods(), [])

    def test_second_save_preserves_metric_not_provided(self):
        save_manual_area(self.repo, '2026-11', '2026-11-01', 'linc', {'dia': {'primary': '100'}})
        snap = save_manual_area(self.repo, '2026-11', '2026-11-02', 'linc', {'mes': {'primary': '500'}})
        self.assertEqual(get_value(snap, 'linc', 'dia'), 100)
        self.assertEqual(get_value(snap, 'linc', 'mes'), 500)

if __name__ == '__main__':
    unittest.main()
