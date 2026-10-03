"""
Implements a performance monitor that records performance statistics for a scheduling server.
"""

from collections import defaultdict as dd


class ServerMonitor:
    """Sample waiting packets/bytes for each observed scheduler class.

    ``sizes`` and ``byte_sizes`` map class IDs to measurement lists. These IDs
    equal flow IDs under the default classifier. Optional service inclusion adds
    the current packet to its mapped class once; downstream retention is excluded.

        Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        server: SPServer, WFQServer, DRRServer, or VirtualClockServer
            The server object to be monitored.
        dist: function
            A no-parameter function that returns the successive inter-arrival
            times of the packets.
        pkt_in_service_included: bool
            If True, monitor packets in service + in the queue;
            If False, only monitor packets in queue.

        To be compatible with this monitor, the scheduling server will need to implement three
        callback functions:

        packet_in_service() -> Packet: returns the current packet being sent to the downstream node

        byte_size(class_id) -> int: returns waiting bytes in a class

        size(class_id) -> int: returns waiting packets in a class

        all_flows() -> list: returns observed class IDs

        flow_classes(packet) -> class ID: maps the packet in service, when supplied;
        a server without this classifier uses packet.flow_id for compatibility.
    """

    def __init__(self, env, server, dist, pkt_in_service_included=False) -> None:
        self.server = server
        self.env = env
        self.dist = dist
        self.pkt_in_service_included = pkt_in_service_included

        self.sizes = dd(list)
        self.byte_sizes = dd(list)

        self.action = env.process(self.run())

    def run(self):
        """Wait one sampling interval, then observe waiting work and service."""
        while True:
            yield self.env.timeout(self.dist())

            current = (
                self.server.packet_in_service()
                if self.pkt_in_service_included else None
            )
            if current is not None:
                classifier = getattr(self.server, "flow_classes", None)
                service_class = (
                    classifier(current) if classifier is not None else current.flow_id
                )

            for class_id in self.server.all_flows():
                total = self.server.size(class_id)
                total_bytes = self.server.byte_size(class_id)
                if current is not None and service_class == class_id:
                    total += 1
                    total_bytes += current.size

                self.sizes[class_id].append(total)
                self.byte_sizes[class_id].append(total_bytes)
