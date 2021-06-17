"""
A monitor for a Port.
"""


class PortMonitor:
    """ Looks at the number of items in the Port, in service + in the queue,
        and records that info in the sizes[] list. The monitor looks at the port
        at time intervals given by the distribution dist.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
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
        """The generator function used in simulations."""
        while True:
            yield self.env.timeout(self.dist())

            if self.pkt_in_service_included:
                total_byte = self.port.byte_size + self.port.busy_packet_size
                total = len(self.port.store.items) + self.port.busy
            else:
                total_byte = self.port.byte_size
                total = len(self.port.store.items)

            self.sizes.append(total)
            self.sizes_byte.append(total_byte)
