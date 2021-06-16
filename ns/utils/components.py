import copy


class TrTCM:
    """ A Two rate three color marker. Uses the flow_id packet field to
        mark the packet with green = 0, yellow = 1, red = 2.

        Parameters
        ----------
        env : the SimPy environment (so we can get the simulated time)
        pir : Peak Information Rate in units of bits (slighly different from RFC)
        pbs : Peak Burst Size in units of bytes
        cir : Committed Information Rate in units of bits (time part maybe scaled)
        cbs : Committed Burst Size in bytes
    """
    def __init__(self, env, pir, pbs, cir, cbs):
        self.env = env
        self.out = None
        self.pir = pir
        self.pbs = pbs
        self.cir = cir
        self.cbs = cbs
        self.pbucket = pbs
        self.cbucket = cbs
        self.last_time = 0.0  # Last time we updated buckets

    def put(self, pkt):
        """ Sends the packet 'pkt' to the next-hop element. """
        time_inc = self.env.now - self.last_time
        self.last_time = self.env.now
        # Add bytes to the buckets
        self.pbucket += self.pir * time_inc / 8.0  # rate in bits, bucket in bytes
        if self.pbucket > self.pbs:
            self.pbucket = self.pbs
        self.cbucket += self.cir * time_inc / 8.0  # rate in bits, bucket in bytes
        if self.cbucket > self.cbs:
            self.cbucket = self.cbs
        # Check marking criteria and mark
        if self.pbucket - pkt.size < 0:
            pkt.flow_id = 2  # Red packet
        elif self.cbucket - pkt.size < 0:
            pkt.flow_id = 1  # Yellow packet
            self.pbucket -= pkt.size
        else:
            pkt.flow_id = 0  # Green packet
            self.pbucket -= pkt.size
            self.cbucket -= pkt.size
        # Send marked packet on its way
        self.out.put(pkt)


class SnoopSplitter:
    """ A snoop port like splitter. Sends the original packet out port 1
        and sends a copy of the packet out port 2.

        You need to set the values of out1 and out2.
    """
    def __init__(self):
        self.out1 = None
        self.out2 = None

    def put(self, pkt):
        """ Sends the packet 'pkt' to the next-hop element. """
        pkt2 = copy.copy(pkt)
        if self.out1:
            self.out1.put(pkt)
        if self.out2:
            self.out2.put(pkt2)
