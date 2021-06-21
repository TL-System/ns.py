import networkx as nx
# based on the FNSS datacenter topology implementation


def build(k):
    """
    Return a fat tree datacenter topology, as described in [1]_

    A fat tree topology built using k-port switches can support up to
    :math:`(k^3)/4` hosts. This topology comprises k pods with two layers of
    :math:`k/2` switches each. In each pod, each aggregation switch is
    connected to all the :math:`k/2` edge switches and each edge switch is
    connected to :math:`k/2` hosts. There are :math:`(k/2)^2` core switches,
    each of them connected to one aggregation switch per pod.

    Each node has three attributes:
     * type: can either be *switch* or *host*
     * tier: can either be *core*, *aggregation*, *edge* or *leaf*. Nodes in
     * pod: the pod id in which the node is located, unless it is a core switch
       the leaf tier are only host, while all core, aggregation and edge
       nodes are switches.

    Each edge has an attribute type as well which can either be *core_edge* if
    it connects a core and an aggregation switch, *aggregation_edge*, if it
    connects an aggregation and a core switch or *edge_leaf* if it connects an
    edge switch to a host.

    Parameters
    ----------
    k: int
        The number of ports of the switches

    Returns
    -------
    topology: a networkx graph

    References
    ----------
    .. [1] M. Al-Fares, A. Loukissas, and A. Vahdat. A scalable, commodity
       data center network architecture. Proceedings of the ACM SIGCOMM 2008
       conference on Data communication (SIGCOMM '08). ACM, New York, NY, USA
       http://doi.acm.org/10.1145/1402958.1402967
    """
    # validate input arguments
    if not isinstance(k, int):
        raise TypeError('k argument must be of int type')
    if k < 1 or k % 2 == 1:
        raise ValueError('k must be a positive even integer')

    topo = nx.Graph()
    topo.name = "fat_tree_topology(%d)" % (k)

    # Create core nodes
    n_core = (k // 2)**2
    topo.add_nodes_from([v for v in range(int(n_core))],
                        layer='core',
                        type='switch')

    # Create aggregation and edge nodes and connect them
    for pod in range(k):
        aggr_start_node = topo.number_of_nodes()
        aggr_end_node = aggr_start_node + k // 2
        edge_start_node = aggr_end_node
        edge_end_node = edge_start_node + k // 2
        aggr_nodes = range(aggr_start_node, aggr_end_node)
        edge_nodes = range(edge_start_node, edge_end_node)
        topo.add_nodes_from(aggr_nodes,
                            layer='aggregation',
                            type='switch',
                            pod=pod)
        topo.add_nodes_from(edge_nodes, layer='edge', type='switch', pod=pod)
        topo.add_edges_from([(u, v) for u in aggr_nodes for v in edge_nodes],
                            type='aggregation_edge')

    # Connect core switches to aggregation switches
    for core_node in range(n_core):
        for pod in range(k):
            aggr_node = n_core + (core_node // (k // 2)) + (k * pod)
            topo.add_edge(core_node, aggr_node, type='core_aggregation')

    # Create hosts and connect them to edge switches
    for u in [v for v in topo.nodes() if topo.nodes[v]['layer'] == 'edge']:
        leaf_nodes = range(topo.number_of_nodes(),
                           topo.number_of_nodes() + k // 2)
        topo.add_nodes_from(leaf_nodes,
                            layer='leaf',
                            type='host',
                            pod=topo.nodes[u]['pod'])
        topo.add_edges_from([(u, v) for v in leaf_nodes], type='edge_leaf')

    return topo
