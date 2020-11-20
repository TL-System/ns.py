
class PortMonitor:
    """ A monitor for an SwitchPort. Looks at the number of items in the SwitchPort
        in service + in the queue and records that info in the sizes[] list. The
        monitor looks at the port at time intervals given by the distribution dist.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        port : SwitchPort
            the switch port object to be monitored.
        dist : function
            a no parameter function that returns the successive inter-arrival times of the
            packets
    """
    def __init__(self, env, port, dist, count_bytes=False):
        self.port = port
        self.env = env
        self.dist = dist
        self.count_bytes = count_bytes
        self.sizes = []
        self.action = env.process(self.run())


    def run(self):
        while True:
            yield self.env.timeout(self.dist())
            if self.count_bytes:
                total = self.port.byte_size
            else:
                total = len(self.port.store.items) + self.port.busy
            self.sizes.append(total)
