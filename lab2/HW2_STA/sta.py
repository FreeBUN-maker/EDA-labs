"""Fill the seven functions; run: python3 run_hw2.py --openroad-root <OpenROAD>.
All times are ns. IDs index sorted pin-name lists, NOT topological order.
graph: nodes; incoming[v]/outgoing[v] = [(neighbor_id, late_delay)];
source_at[s] = clk-q (PI/tie: 0); endpoint_setup[e] = setup;
launch_clock[s] = clock ID (PI/tie: None); capture_clock[e] = clock ID.
clock: nodes, root, parent[v] (root: None), early[v]/late[v] EDGE delays.
FF Q/QN are sources, D pins are sinks. No D-to-Q data edge.
"""

from collections import deque
import math


def topological_order(graph):
    """Return all data IDs in topological order; reject cycles."""
    indegree = [len(edges) for edges in graph.incoming]
    ready = deque(v for v, degree in enumerate(indegree) if degree == 0)
    order = []
    while ready:
        u = ready.popleft()
        order.append(u)
        for v, _ in graph.outgoing[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    if len(order) != len(graph.nodes):
        raise ValueError('data graph contains a cycle')
    return order


def propagate_clock(clock):
    """Return (early, late) absolute clock-arrival lists; root starts at zero."""
    size = len(clock.nodes)
    if not 0 <= clock.root < size or clock.parent[clock.root] is not None:
        raise ValueError('clock must have one root with no parent')
    children = [[] for _ in clock.nodes]
    for v, parent in enumerate(clock.parent):
        if v == clock.root:
            continue
        if parent is None or not 0 <= parent < size:
            raise ValueError('non-root clock pin has no valid parent')
        children[parent].append(v)
    early, late = [0.0] * size, [0.0] * size
    ready = deque([clock.root])
    visited = 0
    while ready:
        u = ready.popleft()
        visited += 1
        for v in children[u]:
            early[v] = early[u] + clock.early[v]
            late[v] = late[u] + clock.late[v]
            ready.append(v)
    if visited != size:
        raise ValueError('clock is not a connected rooted tree')
    return early, late


def propagate_arrival(graph, order, clock_late):
    """Return (arrival, predecessor): source-ID -> data-ID list (None if absent).
    Seed ONLY that source at clk-q + late clock (PI/tie: 0). Propagate max AT;
    exact ties choose smallest parent ID. Keep launches separate.
    """
    arrival, predecessor = {}, {}
    for source in sorted(graph.source_at):
        at = [None] * len(graph.nodes)
        pred = [None] * len(graph.nodes)
        launch = graph.launch_clock[source]
        at[source] = graph.source_at[source] + (
            clock_late[launch] if launch is not None else 0.0)
        for u in order:
            if at[u] is None:
                continue
            for v, delay in graph.outgoing[u]:
                candidate = at[u] + delay
                if (at[v] is None or candidate > at[v]
                        or (candidate == at[v]
                            and (pred[v] is None or u < pred[v]))):
                    at[v], pred[v] = candidate, u
        arrival[source], predecessor[source] = at, pred
    return arrival, predecessor


def propagate_required(graph, order, clock_early, period):
    """Return baseline RAT list: seed e at period + early clock - setup,
    propagate min backwards; unconstrained nodes use float('inf').
    """
    required = [math.inf] * len(graph.nodes)
    for endpoint, setup in graph.endpoint_setup.items():
        required[endpoint] = period + clock_early[graph.capture_clock[endpoint]] - setup
    for u in reversed(order):
        for v, delay in graph.outgoing[u]:
            required[u] = min(required[u], required[v] - delay)
    return required


def compute_cppr(clock, launch_leaf, capture_leaf):
    """Return (cppr, common_pin): sum late-early over the shared clock prefix
    and the last common PIN NAME. PI/tie (launch_leaf=None): (0, None).
    """
    if launch_leaf is None:
        return 0.0, None

    def root_path(leaf):
        path, seen = [], set()
        while leaf is not None:
            if leaf in seen or not 0 <= leaf < len(clock.nodes):
                raise ValueError('invalid clock parent chain')
            seen.add(leaf)
            path.append(leaf)
            leaf = clock.parent[leaf]
        if not path or path[-1] != clock.root:
            raise ValueError('clock pin is not connected to the root')
        return list(reversed(path))

    credit, common = 0.0, None
    for launch, capture in zip(root_path(launch_leaf), root_path(capture_leaf)):
        if launch != capture:
            break
        common = clock.nodes[launch]
        if launch != clock.root:
            credit += clock.late[launch] - clock.early[launch]
    return credit, common


def summarize_endpoints(graph, arrival, clock_early, period):
    """Return dict(pairs, endpoints, before, after). Rows use PIN NAMES:
    pairs: launch, endpoint, arrival, required_before/after, slack_before/after,
           cppr, common_pin, for every reachable pair.
    endpoints (sorted by ID): endpoint, before/after_launch, before/after_slack.
    before/after: wns, tns, worst_endpoint, launch. Re-select minimum slack
    separately; ties: smallest source ID, then endpoint ID. Count e once in TNS.
    """
    pairs, endpoints = [], []
    # Keep numeric IDs for tie-breaking; output rows contain pin names only.
    candidates = {e: [] for e in graph.endpoint_setup}
    for source in sorted(graph.source_at):
        for endpoint in sorted(graph.endpoint_setup):
            at = arrival[source][endpoint]
            if at is None:
                continue
            required = (period + clock_early[graph.capture_clock[endpoint]]
                        - graph.endpoint_setup[endpoint])
            credit, common = compute_cppr(
                graph.clock, graph.launch_clock[source], graph.capture_clock[endpoint])
            row = dict(launch=graph.nodes[source], endpoint=graph.nodes[endpoint],
                       arrival=at, required_before=required, required_after=required + credit,
                       slack_before=required - at, slack_after=required + credit - at,
                       cppr=credit, common_pin=common)
            pairs.append(row)
            candidates[endpoint].append((source, row))

    winners = {'before': [], 'after': []}
    for endpoint in sorted(graph.endpoint_setup):
        row = dict(endpoint=graph.nodes[endpoint])
        for mode in ('before', 'after'):
            if candidates[endpoint]:
                source, pair = min(candidates[endpoint],
                                   key=lambda item: (item[1]['slack_' + mode], item[0]))
                slack = pair['slack_' + mode]
                row[mode + '_launch'], row[mode + '_slack'] = graph.nodes[source], slack
                winners[mode].append((slack, source, endpoint))
            else:
                row[mode + '_launch'], row[mode + '_slack'] = None, None
        endpoints.append(row)

    result = dict(pairs=pairs, endpoints=endpoints)
    for mode in ('before', 'after'):
        worst = min(winners[mode], default=None)
        result[mode] = dict(
            wns=min(0.0, worst[0]) if worst else 0.0,
            tns=sum(min(0.0, slack) for slack, _, _ in winners[mode]),
            worst_endpoint=graph.nodes[worst[2]] if worst else None,
            launch=graph.nodes[worst[1]] if worst else None)
    return result


def trace_critical_path(graph, predecessor, endpoint):
    """Return source-to-endpoint data IDs for ONE launch's predecessor list.
    The runner converts names and writes result.json + node_timing.json.
    """
    path, seen = [], set()
    while endpoint is not None:
        if endpoint in seen or not 0 <= endpoint < len(graph.nodes):
            raise ValueError('invalid predecessor chain')
        seen.add(endpoint)
        path.append(endpoint)
        endpoint = predecessor[endpoint]
    return list(reversed(path))
