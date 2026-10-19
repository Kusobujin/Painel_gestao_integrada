"""Testes de lógica, sem dependência de interface gráfica."""
import json
import tempfile
import unittest
from pathlib import Path

from painel.config import AREAS
from painel.data import Snapshot, SQLiteSnapshotRepository
from painel.metrics import business_days, get_value, set_value, status_of, summary


ROOT = Path(__file__).resolve().parent.parent


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.demo = Snapshot.from_dict(json.loads((ROOT / 'data' / 'exemplo_gerencial.json').read_text(encoding='utf-8')))

    def test_structure_has_twelve_areas(self):
        self.assertEqual(len(AREAS), 12)
        self.assertEqual(len({x.key for x in AREAS}), 12)

    def test_source_has_cached_receiving_values(self):
        self.assertEqual(get_value(self.demo, 'recebimento', 'mes'), 122000)
        self.assertAlmostEqual(get_value(self.demo, 'recebimento', 'percentual'), 122000/600000)

    def test_indicator_status_and_kpis(self):
        self.assertEqual(status_of(0.79), 'critico')
        self.assertEqual(status_of(0.81), 'atencao')
        self.assertEqual(status_of(0.95), 'no_alvo')
        kpis = summary(self.demo, [a.key for a in AREAS])
        self.assertEqual(kpis['areas'], 12)
        self.assertEqual(kpis['known'], 8)

    def test_recalculates_when_actual_changes(self):
        obj = Snapshot.from_dict(json.loads(json.dumps(self.demo.to_dict())))
        set_value(obj, 'logistica', 'mes', 'secondary', 15.5)
        self.assertAlmostEqual(get_value(obj, 'logistica', 'percentual'), 0.5)
        self.assertAlmostEqual(get_value(obj, 'logistica', 'falta'), 0.5)

    def test_repository_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = SQLiteSnapshotRepository(Path(folder) / 'test.db')
            repo.put(self.demo)
            self.assertEqual(repo.periods(), ['2026-10'])
            self.assertEqual(get_value(repo.get('2026-10'), 'linc', 'dia'), 1.0)

    def test_business_days(self):
        from datetime import date
        total, remaining = business_days(date(2026, 10, 5), date(2026, 10, 13))
        self.assertEqual(total, 22)
        self.assertEqual(remaining, 13)


if __name__ == '__main__':
    unittest.main()
