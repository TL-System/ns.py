"""
A monitor for a Port.
"""


class PortMonitor:
    """Samples queued packets/bytes and optionally the port's local service.

    Packets retained for a zero-buffer downstream element count as queued here
    until its release callback, even while that element serves them. The monitor
    looks at the port at time intervals given by the distribution dist.

    Parameters
    ----------
    env: simpy.Environment
        the simulation environment.
    port: Port
        the switch port object to be monitored.
    dist: function
        a no parameter function that returns the successive inter-arrival
        times of the packets
    """

    def __init__(self, env, port, dist, pkt_in_service_included=False):
        self.port = port
        self.env = env
        self.dist = dist
        self.sizes = []
        self.sizes_byte = []
        self.action = env.process(self.run())
        self.pkt_in_service_included = pkt_in_service_included

    def run(self):
        """Wait one sampling interval before each instantaneous occupancy reading."""
        while True:
            yield self.env.timeout(self.dist())

            total_byte = self.port.byte_size
            # Store.get() can hand off a packet before its process resumes; a
            # conservation count also covers that brief transition and packets
            # retained for downstream backpressure, without counting any twice.
            total = (
                self.port.packets_received
                - self.port.packets_dropped
                - self.port._packets_removed
            )
            if not self.pkt_in_service_included:
                total_byte -= self.port.busy_packet_size
                total -= self.port.busy

            self.sizes.append(total)
            self.sizes_byte.append(total_byte)
