from collections.abc import Callable, Hashable, Iterable, Mapping
from random import sample
from typing import Any

import networkx as nx

from ns.flow.flow import Flow


def read_topo(fname: str) -> nx.Graph | None:
    """Read a GraphML topology; unsupported suffixes print a message and return."""
    ftype = ".graphml"
    if fname.endswith(ftype):
        return nx.read_graphml(fname)
    else:
        print(f"{fname} is not GraphML")


def generate_flows(
    G: nx.Graph,
    hosts: Iterable[Any],
    nflows: int,
    size: float | None = None,
    start_time: float | None = None,
    finish_time: float | None = None,
    arrival_dist: Callable[[], float] | None = None,
    size_dist: Callable[[], float] | None = None,
) -> dict[int, Flow]:
    """Choose host pairs and one shortest path for each configured flow."""
    all_flows = dict()
    for flow_id in range(nflows):
        src, dst = sample(sorted(hosts), 2)
        all_flows[flow_id] = Flow(
            flow_id,
            src,
            dst,
            size=size,
            start_time=start_time,
            finish_time=finish_time,
            arrival_dist=arrival_dist,
            size_dist=size_dist,
        )
        all_flows[flow_id].path = sample(list(nx.all_shortest_paths(G, src, dst)), 1)[0]
    return all_flows


def generate_fib(
    G: nx.Graph, all_flows: Mapping[int, Flow], tcp: bool = False,
) -> nx.Graph:
    """Map each path's next hop to a local port, optionally adding reverse ACKs."""
    if tcp:
        # TCPSink identifies ACKs as data flow ID + 10000. Those IDs must remain
        # disjoint from real data flows or later inserts silently change routes.
        flow_ids: set[int] = set()
        for flow in all_flows.values():
            if not isinstance(flow.fid, int):
                raise ValueError("TCP ACK routing requires integer flow IDs.")
            flow_ids.add(flow.fid)
        if any(fid + 10000 in flow_ids for fid in flow_ids):
            raise ValueError("TCP ACK flow IDs collide with data flow IDs.")

    for n in G.nodes():
        node = G.nodes[n]

        node["port_to_nexthop"] = dict()
        node["nexthop_to_port"] = dict()

        for port, nh in enumerate(nx.neighbors(G, n)):
            node["nexthop_to_port"][nh] = port
            node["port_to_nexthop"][port] = nh

        node["flow_to_port"] = dict()
        node["flow_to_nexthop"] = dict()

    for f in all_flows:
        flow = all_flows[f]
        if flow.path is None:
            raise ValueError("Each routed flow requires a path.")
        path = list(zip(flow.path, flow.path[1:]))
        for seg in path:
            a, z = seg
            G.nodes[a]["flow_to_port"][flow.fid] = G.nodes[a]["nexthop_to_port"][z]
            G.nodes[a]["flow_to_nexthop"][flow.fid] = z

            # ACKs retrace the data path through each destination's local port.
            if tcp:
                assert isinstance(flow.fid, int)  # Validated above for ACK IDs.
                G.nodes[z]["flow_to_port"][flow.fid + 10000] = G.nodes[z][
                    "nexthop_to_port"
                ][a]
                G.nodes[z]["flow_to_nexthop"][flow.fid + 10000] = a

    return G
