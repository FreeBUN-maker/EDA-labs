"""Run with python3 -m unittest -v; no third-party packages required."""
import math
import random
from types import SimpleNamespace
import unittest

import sta


def clock_tree():
    # IDs follow names, not tree order: root=3, shared=4, leaves=0/1/2.
    return SimpleNamespace(nodes=['capture', 'launch_far', 'launch_near', 'root', 'shared'],
                           root=3, parent=[4, 3, 4, None, 3],
                           early=[1, 1, 1, 0, 2], late=[2, 2, 2, 0, 6])


def graph_of(names, edges, sources, endpoints, launch=None, capture=None):
    incoming, outgoing = [[] for _ in names], [[] for _ in names]
    for u, v, delay in edges:
        outgoing[u].append((v, delay))
        incoming[v].append((u, delay))
    return SimpleNamespace(nodes=names, incoming=incoming, outgoing=outgoing,
                           clock=clock_tree(), source_at=sources, endpoint_setup=endpoints,
                           launch_clock=launch or {s: None for s in sources},
                           capture_clock=capture or {e: 0 for e in endpoints})


class TimingTests(unittest.TestCase):
    def test_topological_order_is_not_id_order(self):
        graph = graph_of(['sink', 'middle', 'source', 'unused'],
                         [(2, 1, 2), (1, 0, 3)], {2: 0, 3: 0}, {0: 0})
        order = sta.topological_order(graph)
        position = {v: i for i, v in enumerate(order)}
        self.assertEqual(set(order), set(range(4)))
        self.assertLess(position[2], position[1])
        self.assertLess(position[1], position[0])

    def test_data_cycles_rejected(self):
        for edges in [[(0, 0, 0)], [(0, 1, 0), (1, 0, 0)]]:
            with self.assertRaises(ValueError):
                sta.topological_order(graph_of(['a', 'b'], edges, {}, {}))

    def test_clock_propagation_and_root(self):
        clock = clock_tree()
        clock.early[clock.root], clock.late[clock.root] = 100, 200
        self.assertEqual(sta.propagate_clock(clock), ([3, 1, 3, 0, 2], [8, 2, 8, 0, 6]))

    def test_disconnected_clock_cycle_rejected(self):
        clock = clock_tree()
        clock.parent[4] = 0
        with self.assertRaises(ValueError):
            sta.propagate_clock(clock)

    def test_cppr_prefix_leaf_ancestor_and_pi(self):
        clock = clock_tree()
        for launch, capture, expected in [
                (2, 0, (4, 'shared')), (1, 0, (0, 'root')),
                (0, 0, (5, 'capture')), (4, 0, (4, 'shared')),
                (None, 0, (0, None))]:
            self.assertEqual(sta.compute_cppr(clock, launch, capture), expected)

    def test_arrival_ties_and_unreachable_nodes(self):
        graph = graph_of(['end', 'left', 'right', 'source', 'isolated'],
                         [(3, 2, 1), (3, 1, 1), (2, 0, 2), (1, 0, 2)],
                         {3: 0, 4: 0}, {0: 0})
        arrival, pred = sta.propagate_arrival(graph, sta.topological_order(graph), [0] * 5)
        self.assertEqual(arrival[3], [3, 1, 1, 0, None])
        self.assertEqual(arrival[4], [None, None, None, None, 0])
        self.assertEqual(pred[3][0], 1)
        self.assertEqual(sta.trace_critical_path(graph, pred[3], 0), [3, 1, 0])

    def test_required_uses_all_endpoints_and_leaves_infinity(self):
        graph = graph_of(['a', 'b', 'c', 'free'], [(0, 1, 4), (0, 2, 1)],
                         {0: 0, 3: 0}, {1: 1, 2: 3})
        required = sta.propagate_required(graph, sta.topological_order(graph), [3] * 5, 10)
        self.assertEqual(required, [8, 12, 10, math.inf])

    def test_cppr_reselects_worst_launch_and_tns_counts_once(self):
        graph = graph_of(['capture/D', 'far/Q', 'near/Q', 'unused'],
                         [(1, 0, 9), (2, 0, 4)], {1: 0, 2: 0}, {0: 0},
                         {1: 1, 2: 2})
        early, late = sta.propagate_clock(graph.clock)
        arrival, _ = sta.propagate_arrival(graph, sta.topological_order(graph), late)
        result = sta.summarize_endpoints(graph, arrival, early, 6)
        self.assertEqual(result['before']['launch'], 'near/Q')
        self.assertEqual(result['after']['launch'], 'far/Q')
        self.assertEqual((result['before']['wns'], result['before']['tns']), (-3, -3))
        self.assertEqual((result['after']['wns'], result['after']['tns']), (-2, -2))
        self.assertEqual([p['cppr'] for p in result['pairs']], [0, 4])

    def test_summary_ties_use_source_then_endpoint_id(self):
        graph = graph_of(['e0', 'e1', 's0', 's1'], [(3, 0, 10), (2, 1, 10), (3, 1, 10)],
                         {3: 0, 2: 0}, {1: 0, 0: 0})
        at, _ = sta.propagate_arrival(graph, sta.topological_order(graph), [0] * 5)
        result = sta.summarize_endpoints(graph, at, [0] * 5, 8)
        self.assertEqual([e['endpoint'] for e in result['endpoints']], ['e0', 'e1'])
        self.assertEqual(result['before'], dict(wns=-2, tns=-4, worst_endpoint='e1', launch='s0'))

    def test_unconstrained_or_unreachable_endpoints(self):
        graph = graph_of(['source', 'unreachable'], [], {0: 0}, {1: 0})
        at, _ = sta.propagate_arrival(graph, [0, 1], [0] * 5)
        result = sta.summarize_endpoints(graph, at, [0] * 5, 1)
        self.assertEqual(result['pairs'], [])
        self.assertEqual(result['before']['tns'], 0)
        self.assertIsNone(result['endpoints'][0]['before_launch'])

    def test_positive_slack_has_zero_wns(self):
        graph = graph_of(['a', 'b'], [(0, 1, 2)], {0: 0}, {1: 0})
        at, _ = sta.propagate_arrival(graph, [0, 1], [0] * 5)
        result = sta.summarize_endpoints(graph, at, [0] * 5, 10)
        self.assertEqual(result['before']['wns'], 0)
        self.assertEqual(result['endpoints'][0]['before_slack'], 8)

    def test_predecessor_cycle_rejected(self):
        graph = graph_of(['a', 'b'], [], {}, {})
        with self.assertRaises(ValueError):
            sta.trace_critical_path(graph, [1, 0], 0)

    def test_problem2_hand_calculation(self):
        edges = [(0, 4, 5), (1, 4, 10), (2, 5, 10), (4, 6, 15),
                 (6, 7, 15), (5, 7, 25), (7, 8, 15), (3, 8, 30)]
        graph = graph_of(list('ABCDEFGHI'), edges, dict.fromkeys(range(4), 0), {8: 0})
        order = sta.topological_order(graph)
        arrival, _ = sta.propagate_arrival(graph, order, [0] * 5)
        at = [max(a[v] for a in arrival.values() if a[v] is not None) for v in order]
        self.assertEqual(dict(zip(order, at)), dict(enumerate([0, 0, 0, 0, 10, 10, 25, 40, 55])))
        self.assertEqual(sta.propagate_required(graph, order, [0] * 5, 50),
                         [0, -5, 0, 20, 5, 10, 20, 35, 50])

    def test_random_dags_against_exhaustive_path_enumeration(self):
        rng = random.Random(2300012831)
        for case in range(100):
            n = rng.randrange(4, 10)
            shuffled = list(range(n))
            rng.shuffle(shuffled)
            edges = [(shuffled[i], shuffled[j], rng.randrange(5))
                     for i in range(n) for j in range(i + 1, n) if rng.random() < 0.3]
            sources = {v: rng.randrange(3) for v in range(n) if not any(t == v for _, t, _ in edges)}
            endpoints = {v: rng.randrange(3) for v in range(n) if not any(s == v for s, _, _ in edges)}
            launch = {s: rng.choice([None, 1, 2]) for s in sources}
            graph = graph_of([f'n{i}' for i in range(n)], edges, sources, endpoints, launch)
            early, late = sta.propagate_clock(graph.clock)
            order = sta.topological_order(graph)
            arrival, pred = sta.propagate_arrival(graph, order, late)

            def paths(v, length=0):
                yield v, length
                for target, delay in graph.outgoing[v]:
                    yield from paths(target, length + delay)

            for source in sources:
                baseline = sources[source] + (late[launch[source]] if launch[source] is not None else 0)
                expected = [None] * n
                for v, length in paths(source):
                    expected[v] = max(expected[v] if expected[v] is not None else -math.inf,
                                      baseline + length)
                self.assertEqual(arrival[source], expected, f'case {case}, source {source}')
                for end in endpoints:
                    if expected[end] is not None:
                        path = sta.trace_critical_path(graph, pred[source], end)
                        self.assertEqual(path[0], source)
                        distance = sum(dict(graph.outgoing[u])[v] for u, v in zip(path, path[1:]))
                        self.assertEqual(baseline + distance, expected[end])

            period = 8
            reference_rat = [min((period + early[0] - endpoints[e] - d
                                  for e, d in paths(v) if e in endpoints), default=math.inf)
                             for v in range(n)]
            self.assertEqual(sta.propagate_required(graph, order, early, period), reference_rat)
            result = sta.summarize_endpoints(graph, arrival, early, period)
            for mode in ['before', 'after']:
                expected = []
                for e in endpoints:
                    choices = []
                    for s in sources:
                        if arrival[s][e] is not None:
                            credit = 4 if launch[s] == 2 and mode == 'after' else 0
                            choices.append((period + early[0] - endpoints[e] + credit - arrival[s][e], s, e))
                    expected.append(min(choices))
                worst = min(expected)
                self.assertEqual(result[mode]['wns'], min(0, worst[0]))
                self.assertEqual(result[mode]['tns'], sum(min(0, item[0]) for item in expected))
                self.assertEqual(result[mode]['launch'], graph.nodes[worst[1]])
                self.assertEqual(result[mode]['worst_endpoint'], graph.nodes[worst[2]])


if __name__ == '__main__':
    unittest.main()
