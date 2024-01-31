from random import sample
import networkx as nx

from ns.flow.flow import Flow


def read_topo(fname):
    ftype = ".graphml"
    if fname.endswith(ftype):
        return nx.read_graphml(fname)
    else:
        print(f"{fname} is not GraphML")


def generate_flows(
    G,
    hosts,
    nflows,
    size=None,
    start_time=None,
    finish_time=None,
    arrival_dist=None,
    size_dist=None,
):
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
        # all_flows[flow_id].path = sample(
        #    list(nx.all_simple_paths(G, src, dst, cutoff=nx.diameter(G))), 1
        all_flows[flow_id].path = sample(list(nx.all_shortest_paths(G, src, dst)), 1)[0]
    return all_flows


def generate_fib(G, all_flows, tcp=False):
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
        path = list(zip(flow.path, flow.path[1:]))
        for seg in path:
            a, z = seg
            G.nodes[a]["flow_to_port"][flow.fid] = G.nodes[a]["nexthop_to_port"][z]
            G.nodes[a]["flow_to_nexthop"][flow.fid] = z

            # generates reverse fib for TCPSink sending Ack to TCPSource
            if tcp:
                G.nodes[z]["flow_to_port"][flow.fid + 10000] = G.nodes[z][
                    "nexthop_to_port"
                ][a]
                G.nodes[z]["flow_to_nexthop"][flow.fid + 10000] = a

    return G
