#!/usr/bin/env python3
"""Exact, deterministic calculations for Problems 1 and 2 (standard library)."""
import argparse
import json
from collections import defaultdict, deque
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path

VERTICES = tuple("abcdefgh")
NETS = tuple(map(set, ("abc", "bdef", "cfg", "ag", "deh", "fh")))


def problem1():
    weights = defaultdict(F)
    for net in NETS:
        for u, v in combinations(sorted(net), 2):
            weights[u, v] += F(1, len(net) - 1)

    def weight(u, v):
        return weights.get(tuple(sorted((u, v))), F(0))

    def graph_cut(a):
        return sum((w for (u, v), w in weights.items() if (u in a) != (v in a)), F(0))

    def net_cut(a):
        return sum(bool(net & a) and bool(net - a) for net in NETS)

    a = set("abcd")
    unlocked = set(VERTICES)
    initial_cut = graph_cut(a)
    kl, states, cumulative = [], [a.copy()], F(0)
    initial_d = None
    while unlocked:
        d = {u: sum((weight(u, v) * (-1 if (u in a) == (v in a) else 1)
                     for v in VERTICES if u != v), F(0)) for u in sorted(unlocked)}
        if initial_d is None:
            initial_d = d.copy()
        candidates = [(d[u] + d[v] - 2 * weight(u, v), u, v)
                      for u in sorted(unlocked & a) for v in sorted(unlocked - a)]
        gain, u, v = min(candidates, key=lambda t: (-t[0], t[1], t[2]))
        before = graph_cut(a)
        a.remove(u)
        a.add(v)
        unlocked -= {u, v}
        cumulative += gain
        assert before - graph_cut(a) == gain
        kl.append({"pair": [u, v], "d_before": d, "gain": gain,
                   "cumulative": cumulative, "cut": graph_cut(a),
                   "a": sorted(a), "b": sorted(set(VERTICES) - a)})
        states.append(a.copy())
    prefix = max(range(5), key=lambda i: F(0) if i == 0 else kl[i - 1]["cumulative"])
    kl_final = sorted(states[prefix])

    a = set("abcd")
    unlocked = set(VERTICES)
    fm, fm_states, cuts = [], [a.copy()], [net_cut(a)]
    while unlocked:
        gains = {u: net_cut(a) - net_cut(a ^ {u}) for u in sorted(unlocked)}
        legal = [u for u in sorted(unlocked) if 3 <= len(a ^ {u}) <= 5]
        if not legal:
            break
        u = min(legal, key=lambda u: (-gains[u], u))
        a ^= {u}
        unlocked.remove(u)
        fm.append({"cell": u, "gains_before": gains, "legal": legal,
                   "gain": gains[u], "cut": net_cut(a), "a": sorted(a),
                   "b": sorted(set(VERTICES) - a)})
        fm_states.append(a.copy())
        cuts.append(net_cut(a))
    fm_prefix = min(range(len(cuts)), key=cuts.__getitem__)

    queue, parent, discovery = deque(["a"]), {"a": None}, ["a"]
    while queue and "h" not in parent:
        u = queue.popleft()
        for v in VERTICES:
            if weight(u, v) > 0 and v not in parent:
                parent[v] = u
                discovery.append(v)
                queue.append(v)
                if v == "h":
                    break
    path = ["h"]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    path.reverse()
    bottleneck = min(weight(u, v) for u, v in zip(path, path[1:]))
    arcs = [{"u": u, "v": v, "capacity": weight(u, v), "flow": bottleneck,
             "forward_residual": weight(u, v) - bottleneck,
             "reverse_residual": weight(u, v) + bottleneck}
            for u, v in zip(path, path[1:])]
    return {"edges": [{"u": u, "v": v, "w": w} for (u, v), w in sorted(weights.items())],
            "initial_d": initial_d, "initial_graph_cut": initial_cut,
            "kl": kl, "kl_prefix": prefix, "kl_final_a": kl_final,
            "initial_hypergraph_cut": cuts[0], "fm": fm,
            "fm_prefix": fm_prefix, "fm_final_a": sorted(fm_states[fm_prefix]),
            "bfs_discovery": discovery, "augmenting_path": path,
            "bottleneck": bottleneck, "path_arcs": arcs}


def problem2():
    p, n = [1, 7, 4, 5, 2, 6, 3, 8], [8, 4, 7, 2, 5, 3, 6, 1]
    widths = dict(enumerate([2, 1, 3, 3, 3, 5, 1, 2], 1))
    heights = dict(enumerate([4, 3, 3, 5, 2, 3, 2, 4], 1))
    horizontal, vertical = [], []
    for k, i in enumerate(p):
        for j in p[k + 1:]:
            if n.index(i) < n.index(j):
                horizontal.append([i, j, widths[i]])
            else:
                vertical.append([i, j, heights[i]])
    x, y = dict.fromkeys(p, 0), dict.fromkeys(p, 0)
    x_path, y_path = {i: [i] for i in p}, {i: [i] for i in p}
    for i in p:
        for edges, coord, paths in ((horizontal, x, x_path), (vertical, y, y_path)):
            for u, v, w in edges:
                if u == i and coord[u] + w > coord[v]:
                    coord[v] = coord[u] + w
                    paths[v] = paths[u] + [v]
    right = max(p, key=lambda i: x[i] + widths[i])
    top = max(p, key=lambda i: y[i] + heights[i])
    W, H = x[right] + widths[right], y[top] + heights[top]
    relations = []
    for i in range(1, 9):
        relations.append({"i": i,
                          "left_of": sorted(v for u, v, _ in horizontal if u == i),
                          "right_of": sorted(u for u, v, _ in horizontal if v == i),
                          "above": sorted(u for u, v, _ in vertical if v == i),
                          "below": sorted(v for u, v, _ in vertical if u == i)})
    return {"P": p, "N": n, "horizontal": horizontal, "vertical": vertical,
            "relations": relations, "W": W, "H": H, "area": W * H,
            "x_critical_path": x_path[right], "y_critical_path": y_path[top],
            "modules": [{"i": i, "w": widths[i], "h": heights[i], "x": x[i], "y": y[i]}
                        for i in range(1, 9)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="theory_results.json")
    args = ap.parse_args()
    result = {"problem1": problem1(), "problem2": problem2()}
    Path(args.out).write_text(json.dumps(result, default=str, indent=2) + "\n")
    a, b = result["problem1"], result["problem2"]
    print(f"KL: prefix={a['kl_prefix']}, A={a['kl_final_a']}")
    print(f"FM: prefix={a['fm_prefix']}, A={a['fm_final_a']}")
    print(f"BFS: {a['augmenting_path']}, bottleneck={a['bottleneck']}")
    print(f"SP: W={b['W']}, H={b['H']}, area={b['area']}")


if __name__ == "__main__":
    main()
