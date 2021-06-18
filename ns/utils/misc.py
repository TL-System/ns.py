"""
Implements a two rate three color marker. It uses the flow_id packet field to mark each
packet with green = 0, yellow = 1, red = 2.

Reference:

RFC 2698: A Two Rate Three Color Marker

https://datatracker.ietf.org/doc/html/rfc2698
"""


class TrTCM:
    """ A Two rate three color marker. Uses the flow_id packet field to
        mark the packet with green = 0, yellow = 1, red = 2.

        Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        pir: int
            The Peak Information Rate in units of bits (slighly different from RFC).
        pbs: int
            The Peak Burst Size in units of bytes.
        cir: int
            The Committed Information Rate in units of bits.
        cbs: int
            The Committed Burst Size in bytes.
    """
    def __init__(self, env, pir: int, pbs: int, cir, cbs):
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
        """ Sends the packet 'pkt' to this element. """
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
