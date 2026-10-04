"""Hand-counted FatTrees and real packet forwarding through generated FIBs."""

from itertools import combinations

import networkx as nx
import pytest
import simpy

from ns.flow.flow import Flow
from ns.packet.packet import Packet
from ns.packet.sink import PacketSink
from ns.switch.switch import SimplePacketSwitch
from ns.topos.fattree import build
from ns.topos.utils import generate_fib, generate_flows, read_topo


@pytest.mark.parametrize(
    "k,cores,aggregation,edges,hosts,links",
    [(2, 1, 2, 2, 2, 6), (4, 4, 8, 8, 16, 48)],
)
def test_fattree_counts_degrees_and_symmetric_host_distances(
    k, cores, aggregation, edges, hosts, links
):
    graph = build(k)
    expected = {"core": cores, "aggregation": aggregation, "edge": edges, "leaf": hosts}
    for layer, count in expected.items():
        nodes = [
            node for node, data in graph.nodes(data=True) if data["layer"] == layer
        ]
        assert len(nodes) == count
        degree = 1 if layer == "leaf" else k
        assert all(graph.degree[node] == degree for node in nodes)
    assert graph.number_of_edges() == links
    assert nx.is_connected(graph)
    leaves = [node for node, data in graph.nodes(data=True) if data["type"] == "host"]
    for source, target in combinations(leaves, 2):
        if next(graph.neighbors(source)) == next(graph.neighbors(target)):
            distance = 2
        elif graph.nodes[source]["pod"] == graph.nodes[target]["pod"]:
            distance = 4
        else:
            distance = 6
        assert nx.shortest_path_length(graph, source, target) == distance
        assert nx.shortest_path_length(graph, target, source) == distance


@pytest.mark.parametrize(
    "k,exception",
    [(0, ValueError), (1, ValueError), (-2, ValueError), (3, ValueError),
     (2.0, TypeError), ("4", TypeError)],
)
def test_fattree_rejects_nonpositive_odd_or_noninteger_k(k, exception):
    with pytest.raises(exception):
        build(k)


@pytest.mark.parametrize("k", [2, 4])
def test_fib_forward_and_ack_paths_deliver_with_hand_calculated_link_times(k):
    graph = build(k)
    leaves = [node for node, data in graph.nodes(data=True) if data["type"] == "host"]
    source, target = leaves[0], leaves[-1]
    path = nx.shortest_path(graph, source, target)
    flow = Flow(17, source, target, path=path)
    generate_fib(graph, {17: flow}, tcp=True)
    env = simpy.Environment()
    for node, data in graph.nodes(data=True):
        device = SimplePacketSwitch(
            env, graph.degree[node], 800, 10, element_id=str(node)
        )
        data["device"] = device
        device.demux.fib = data["flow_to_port"]
        reverse = {
            port: neighbor for neighbor, port in data["nexthop_to_port"].items()
        }
        assert reverse == data["port_to_nexthop"]
    for node, data in graph.nodes(data=True):
        for port, neighbor in data["port_to_nexthop"].items():
            data["device"].ports[port].out = graph.nodes[neighbor]["device"]
    data_sink, ack_sink = PacketSink(env), PacketSink(env)
    graph.nodes[target]["device"].demux.ends[17] = data_sink
    graph.nodes[source]["device"].demux.ends[10017] = ack_sink
    data, ack = Packet(0, 100, 1, flow_id=17), Packet(0, 40, 2, flow_id=10017)
    graph.nodes[source]["device"].put(data)
    graph.nodes[target]["device"].put(ack)
    env.run()
    # Cross-pod hosts require six links. Each link takes 1 s for data or .4 s
    # for the ACK at 800 bits/s; opposite directions use independent ports.
    assert len(path) - 1 == 6
    assert data_sink.arrivals[17] == [6]
    assert ack_sink.arrivals[10017] == pytest.approx([2.4])
    assert data_sink.bytes_received[17] == 100
    assert ack_sink.bytes_received[10017] == 40
    for before, after in zip(path, path[1:]):
        assert graph.nodes[before]["flow_to_nexthop"][17] == after
        assert graph.nodes[after]["flow_to_nexthop"][10017] == before
    assert all(
        data["device"].demux.packets_dropped == 0
        for _, data in graph.nodes(data=True)
    )


def test_generated_flows_choose_explicit_endpoint_pair_and_shortest_path(monkeypatch):
    graph = build(4)
    hosts = {node for node, data in graph.nodes(data=True) if data["type"] == "host"}

    def select(population, count):
        return [population[0], population[-1]] if count == 2 else [population[-1]]

    monkeypatch.setattr("ns.topos.utils.sample", select)
    flow = generate_flows(graph, hosts, 1, size=140, start_time=2)[0]
    assert (flow.src, flow.dst, flow.size, flow.start_time) == (
        min(hosts), max(hosts), 140, 2
    )
    assert (flow.path[0], flow.path[-1]) == (flow.src, flow.dst)
    assert len(flow.path) - 1 == 6
    assert all(graph.has_edge(a, b) for a, b in zip(flow.path, flow.path[1:]))


def test_graphml_roundtrip_uses_current_networkx_api(tmp_path):
    path = tmp_path / "topology.graphml"
    nx.write_graphml(build(2), path)
    graph = read_topo(str(path))
    assert (graph.number_of_nodes(), graph.number_of_edges()) == (7, 6)
    assert graph.nodes["0"]["layer"] == "core"


def test_tcp_fib_rejects_data_ack_id_collision_before_overwriting_routes():
    graph = build(2)
    path = [5, 2, 1, 0, 3, 4, 6]
    flows = {
        0: Flow(0, 5, 6, path=path),
        10000: Flow(10000, 6, 5, path=path[::-1]),
    }
    with pytest.raises(ValueError, match="ACK.*collide"):
        generate_fib(graph, flows, tcp=True)
    assert all("flow_to_port" not in data for _, data in graph.nodes(data=True))
