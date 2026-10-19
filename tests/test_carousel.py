"""Testes da paginação, estados e comportamento em falta de dados."""
import unittest
from painel.carousel import paginate_areas, status_presentation, ease_in_out_cubic, centered_group_geometry


class CarouselTests(unittest.TestCase):
    def test_twelve_areas_in_groups_of_three(self):
        pages = paginate_areas(list(range(12)), 3)
        self.assertEqual(len(pages), 4)
        self.assertEqual([n for page in pages for n in page], list(range(12)))

    def test_incomplete_last_page(self):
        self.assertEqual(paginate_areas(list(range(12)), 5)[-1], [10, 11])

    def test_empty_and_single_area(self):
        self.assertEqual(paginate_areas([], 3), [])
        self.assertEqual(paginate_areas(['LINC'], 3), [['LINC']])

    def test_invalid_page_size(self):
        with self.assertRaises(ValueError):
            paginate_areas(range(12), 0)

    def test_centered_two_card_geometry(self):
        x, w = centered_group_geometry(1920, 2)
        self.assertEqual(x * 2 + w, 1920)
        self.assertGreater(x, 100)
        self.assertLess(w, 1400)

    def test_easing_has_smooth_edges(self):
        self.assertEqual(ease_in_out_cubic(0), 0)
        self.assertEqual(ease_in_out_cubic(1), 1)
        self.assertAlmostEqual(ease_in_out_cubic(.5), .5)
        self.assertLess(ease_in_out_cubic(.1), .1)
        self.assertGreater(ease_in_out_cubic(.9), .9)

    def test_status_labels(self):
        self.assertEqual(status_presentation(None)[0], 'SEM DADOS')
        self.assertEqual(status_presentation(.50)[0], 'CRÍTICO')
        self.assertEqual(status_presentation(.85)[0], 'ATENÇÃO')
        self.assertEqual(status_presentation(.95)[0], 'NO ALVO')

if __name__ == '__main__':
    unittest.main()
