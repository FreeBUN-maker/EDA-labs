#!/usr/bin/env python3
"""Algorithm checks independent of OpenROAD and the checker snapshot."""
import random
import unittest
from unittest.mock import patch

import hw3
from solve_theory import problem1, problem2


class PackingTests(unittest.TestCase):
    def test_problem2_known_optimum(self):
        p = problem2()
        macros = [hw3.Macro(str(m['i']), '', m['w'], m['h']) for m in p['modules']]
        d = hw3.Design('eight', (0, 0, 100, 100), macros, [])
        with patch.object(hw3, 'HALO', 0):
            coords, w, h = hw3.pack(d, [i - 1 for i in p['P']],
                                   [i - 1 for i in p['N']], [0] * 8)
        self.assertEqual((w, h), (11, 15))
        self.assertEqual(coords, [(0, 0), (3, 6), (6, 7), (0, 6),
                                  (3, 4), (6, 4), (0, 4), (0, 11)])

    def test_random_constraints_and_minimality(self):
        rng = random.Random(2026)
        for _ in range(100):
            n = rng.randrange(2, 13)
            macros = [hw3.Macro(str(i), '', rng.randint(1, 50), rng.randint(1, 50))
                      for i in range(n)]
            d = hw3.Design('random', (0, 0, 10000, 10000), macros, [])
            p, q = rng.sample(range(n), n), rng.sample(range(n), n)
            coords, w, h = hw3.pack(d, p, q, [rng.randrange(4) for _ in range(n)])
            # Independent relaxation without relying on P as a topological order.
            distances = [[0.0, 0.0] for _ in range(n)]
            for _round in range(n):
                for i in range(n):
                    for j in range(n):
                        if p.index(i) >= p.index(j):
                            continue
                        axis = 0 if q.index(i) < q.index(j) else 1
                        size = macros[i].w if axis == 0 else macros[i].h
                        distances[j][axis] = max(distances[j][axis],
                                                 distances[i][axis] + size + hw3.HALO)
            self.assertEqual(coords, [tuple(xy) for xy in distances])
            for i in range(n):
                for j in range(i):
                    xi, yi = coords[i]
                    xj, yj = coords[j]
                    self.assertTrue(xi + macros[i].w + hw3.HALO <= xj
                                    or xj + macros[j].w + hw3.HALO <= xi
                                    or yi + macros[i].h + hw3.HALO <= yj
                                    or yj + macros[j].h + hw3.HALO <= yi)
            self.assertEqual(w, max(x + m.w + hw3.HALO for (x, _), m in zip(coords, macros)))
            self.assertEqual(h, max(y + m.h + hw3.HALO for (_, y), m in zip(coords, macros)))

    def test_invalid_permutations(self):
        d = hw3.Design('two', (0, 0, 100, 100), [hw3.Macro('', '', 1, 1)] * 2, [])
        for p, n, o in [([0, 0], [0, 1], [0, 0]), ([0, 1], [0], [0, 0]),
                        ([0, 1], [0, 1], [0, 4])]:
            self.assertIsNone(hw3.pack(d, p, n, o))


class HPWLTests(unittest.TestCase):
    def test_all_orientations_and_translation(self):
        m = hw3.Macro('a', 'm', 10, 20, {'p': (2, 3)})
        other = hw3.Macro('b', 'm', 5, 5, {'q': (0, 0)})
        d = hw3.Design('pins', (0, 0, 100, 100), [m, other],
                       [[(0, 'p'), (1, 'q')], [(0, 'p')], []])
        for orient, expected in enumerate([65, 51, 59, 45]):
            self.assertEqual(hw3.macro_hpwl(d, [(0, 0), (30, 40)], [orient, 0]), expected)
            self.assertEqual(hw3.macro_hpwl(d, [(7, 9), (37, 49)], [orient, 0]), expected)

    def test_multiple_pins_of_same_macro(self):
        m = hw3.Macro('a', 'm', 10, 20, {'p': (2, 3), 'q': (8, 17)})
        d = hw3.Design('same', (0, 0, 100, 100), [m], [[(0, 'p'), (0, 'q')]])
        self.assertEqual(hw3.macro_hpwl(d, [(100, 100)], [3]), 20)

    def test_area_is_not_an_additive_cost(self):
        d = hw3.Design('two', (0, 0, 1000, 1000),
                       [hw3.Macro('a', '', 10, 10), hw3.Macro('b', '', 20, 5)], [])
        self.assertEqual(hw3._cost(d, [0, 1], [0, 1], [0, 0])[0], 0)
        self.assertEqual(hw3._cost(d, [0, 1], [1, 0], [0, 0])[0], 0)


class TheoryTests(unittest.TestCase):
    def test_exact_pass_results(self):
        p = problem1()
        self.assertEqual(p['kl_prefix'], 1)
        self.assertEqual(p['fm_prefix'], 2)
        self.assertEqual(p['kl_final_a'], list('abcg'))
        self.assertEqual(p['fm_final_a'], list('abcg'))
        self.assertEqual(p['augmenting_path'], list('abdh'))
        self.assertEqual(str(p['bottleneck']), '1/3')


if __name__ == '__main__':
    unittest.main(verbosity=2)
