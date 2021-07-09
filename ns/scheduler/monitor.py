"""
Implements a performance monitor that records performance statistics for a scheduling server.
"""
from collections import defaultdict as dd


class ServerMonitor:
    """ Looks at the number of packets for each of the flows in a server, in service +
    in the queue, and records that info in sizes and byte_sizes, both of which are dictionaries
    that map flow ids to lists of measurements. The server monitor looks at the flow queues
    at time intervals given by the distribution `dist`.

        Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        server: SPServer, WFQServer, or DRRServer
            The server object to be monitored.
        dist: function
            A no-parameter function that returns the successive inter-arrival
            times of the packets.
        total_flows: int
            The total number of flows to be monitored.
        pkt_in_service_included: bool
            If True, monitor packets in service + in the queue;
            If False, only monitor packets in queue.

        To be compatible with this monitor, the scheduling server will need to implement three
        callback functions:
        
        packet_in_service() -> Packet: returns the current packet being sent to the downstream node

        byte_size(flow_id) -> int: returns the queue length in bytes for a flow with a
        particular flow ID

        size(flow_id) -> int: returns the queue length in the number of packets for a
        flow with a particular flow ID

        all_flows -> list: returns a list containing all the flow IDs
    """
    def __init__(self,
                 env,
                 server,
                 dist,
                 pkt_in_service_included=False) -> None:

        self.server = server
        self.env = env
        self.dist = dist
        self.pkt_in_service_included = pkt_in_service_included

        self.sizes = dd(list)
        self.byte_sizes = dd(list)

        self.action = env.process(self.run())

    def run(self):
        """The generator function used in simulations."""
        while True:
            yield self.env.timeout(self.dist())

            for flow_id in self.server.all_flows():
                total = self.server.size(flow_id)
                total_bytes = self.server.byte_size(flow_id)

                if self.pkt_in_service_included:
                    if self.server.packet_in_service() is not None:
                        if self.server.packet_in_service().flow_id == flow_id:
                            total += 1
                            total_bytes += self.server.packet_in_service().size

                self.sizes[flow_id].append(total)
                self.byte_sizes[flow_id].append(total_bytes)
