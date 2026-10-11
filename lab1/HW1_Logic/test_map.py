#!/usr/bin/env python3
"""Small adversarial cases for matching and dual-polarity covering."""

from pathlib import Path
import unittest

from aig import Subject
from map import cover, load_lib, matches_at


LIBRARY = load_lib(Path(__file__).resolve().parent / "fixtures/lib.json")
GATES = {g["name"]: g for g in LIBRARY}


def subject(ands, inputs=2):
    return Subject(inputs=[(2 * v, f"i{v}") for v in range(1, inputs + 1)],
                   ands=ands, order=list(ands))


class MatcherTests(unittest.TestCase):
    def test_child_orders_and_duplicate_bindings(self):
        self.assertEqual(list(matches_at(GATES["and2"], 3,
                                         subject({3: (2, 4)}))),
                         [{"a": 2, "b": 4}, {"a": 4, "b": 2}])
        self.assertEqual(list(matches_at(GATES["and2"], 3,
                                         subject({3: (2, 2)}))),
                         [{"a": 2, "b": 2}])
        self.assertEqual(list(matches_at(GATES["inv1"], 3,
                                         subject({3: (2, 4)}))), [])

    def test_leaf_inversion_is_absorbed_into_binding(self):
        self.assertEqual(list(matches_at(GATES["nor2"], 3,
                                         subject({3: (3, 4)}))),
                         [{"a": 2, "b": 5}, {"a": 5, "b": 2}])

    def test_nested_child_swap_and_exact_internal_polarity(self):
        # Pattern's left child must match the subject's right child.
        good = subject({4: (2, 4), 5: (6, 8)}, inputs=3)
        self.assertEqual(list(matches_at(GATES["and3"], 5, good)),
                         [{"a": 2, "b": 4, "c": 6},
                          {"a": 4, "b": 2, "c": 6}])
        bad = subject({4: (2, 4), 5: (6, 9)}, inputs=3)
        self.assertEqual(list(matches_at(GATES["and3"], 5, bad)), [])

    def test_xor_repeated_pins_must_agree(self):
        good = subject({4: (2, 5), 5: (3, 4), 6: (9, 11)}, inputs=3)
        matches = list(matches_at(GATES["xor2"], 6, good))
        self.assertIn({"a": 2, "b": 4}, matches)
        self.assertEqual(len(matches), 4)
        # Replace one occurrence of b by c. Topology still matches XOR,
        # but no consistent pin assignment exists.
        bad = subject({4: (2, 5), 5: (3, 6), 6: (9, 11)}, inputs=3)
        self.assertEqual(list(matches_at(GATES["xor2"], 6, bad)), [])


class CoverTests(unittest.TestCase):
    def test_primary_inputs_and_missing_direct_polarity(self):
        gates = [GATES["inv1"], GATES["nand2"]]
        costs, choices = cover(subject({3: (2, 4)}), gates)
        self.assertEqual(costs[1], [0.0, 0.04374])
        self.assertEqual(choices[1], [None, ("inv",)])
        self.assertAlmostEqual(costs[3][0], 0.13122)
        self.assertAlmostEqual(costs[3][1], 0.08748)
        self.assertEqual(choices[3][0], ("inv",))
        self.assertEqual(choices[3][1][3]["name"], "nand2")

    def test_inverter_can_beat_an_existing_direct_gate(self):
        expensive = {**GATES["and2"], "area": 1.0}
        costs, choices = cover(subject({3: (2, 4)}),
                               [GATES["inv1"], expensive, GATES["nand2"]])
        self.assertAlmostEqual(costs[3][0], 0.13122)
        self.assertEqual(choices[3][0], ("inv",))
        self.assertEqual(choices[3][1][0], "gate")

    def test_shared_leaf_is_charged_once_per_literal(self):
        gates = [GATES["inv1"], GATES["and2"]]
        costs, choices = cover(subject({3: (2, 4), 4: (7, 7)}), gates)
        self.assertAlmostEqual(costs[4][0], 0.21870)
        self.assertEqual(choices[4][0][2], [7])
        # Opposite polarities of one variable are two distinct literals.
        costs, choices = cover(subject({3: (2, 4), 4: (6, 7)}), gates)
        self.assertAlmostEqual(costs[4][0], 0.30618)
        self.assertEqual(choices[4][0][2], [6, 7])

    def test_ties_preserve_library_and_child_order(self):
        first = {**GATES["and2"], "name": "first"}
        gates = [GATES["inv1"], first, GATES["and2"]]
        _, choices = cover(subject({3: (2, 4)}), gates)
        self.assertEqual(choices[3][0][3]["name"], "first")
        self.assertEqual(choices[3][0][1], {"a": 2, "b": 4})
        # Exact integer costs also exercise a direct/inverter-route tie.
        gates = [{**GATES["inv1"], "area": 1},
                 {**GATES["nand2"], "area": 1},
                 {**GATES["and2"], "area": 2}]
        _, choices = cover(subject({3: (2, 4)}), gates)
        self.assertEqual(choices[3][0][3]["name"], "and2")


if __name__ == "__main__":
    unittest.main()
