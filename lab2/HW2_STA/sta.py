"""Fill the seven functions; run: python3 run_hw2.py --openroad-root <OpenROAD>.
All times are ns. IDs index sorted pin-name lists, NOT topological order.
graph: nodes; incoming[v]/outgoing[v] = [(neighbor_id, late_delay)];
source_at[s] = clk-q (PI/tie: 0); endpoint_setup[e] = setup;
launch_clock[s] = clock ID (PI/tie: None); capture_clock[e] = clock ID.
clock: nodes, root, parent[v] (root: None), early[v]/late[v] EDGE delays.
FF Q/QN are sources, D pins are sinks. No D-to-Q data edge.
"""


def topological_order(graph):
    """Return all data IDs in topological order; reject cycles."""
    raise NotImplementedError('topological_order')


def propagate_clock(clock):
    """Return (early, late) absolute clock-arrival lists; root starts at zero."""
    raise NotImplementedError('propagate_clock')


def propagate_arrival(graph, order, clock_late):
    """Return (arrival, predecessor): source-ID -> data-ID list (None if absent).
    Seed ONLY that source at clk-q + late clock (PI/tie: 0). Propagate max AT;
    exact ties choose smallest parent ID. Keep launches separate.
    """
    raise NotImplementedError('propagate_arrival')


def propagate_required(graph, order, clock_early, period):
    """Return baseline RAT list: seed e at period + early clock - setup,
    propagate min backwards; unconstrained nodes use float('inf').
    """
    raise NotImplementedError('propagate_required')


def compute_cppr(clock, launch_leaf, capture_leaf):
    """Return (cppr, common_pin): sum late-early over the shared clock prefix
    and the last common PIN NAME. PI/tie (launch_leaf=None): (0, None).
    """
    raise NotImplementedError('compute_cppr')


def summarize_endpoints(graph, arrival, clock_early, period):
    """Return dict(pairs, endpoints, before, after). Rows use PIN NAMES:
    pairs: launch, endpoint, arrival, required_before/after, slack_before/after,
           cppr, common_pin, for every reachable pair.
    endpoints (sorted by ID): endpoint, before/after_launch, before/after_slack.
    before/after: wns, tns, worst_endpoint, launch. Re-select minimum slack
    separately; ties: smallest source ID, then endpoint ID. Count e once in TNS.
    """
    raise NotImplementedError('summarize_endpoints')


def trace_critical_path(graph, predecessor, endpoint):
    """Return source-to-endpoint data IDs for ONE launch's predecessor list.
    The runner converts names and writes result.json + node_timing.json.
    """
    raise NotImplementedError('trace_critical_path')
