"""
Implements a two rate tricolor marker. It uses the flow_id packet field to mark each
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
        self.peak_bucket = pbs
        self.committed_bucket = cbs
        self.last_time = 0.0  # Last time we updated buckets

    def put(self, packet):
        """ Sends a packet to this element. """
        time_inc = self.env.now - self.last_time
        self.last_time = self.env.now
        # Add bytes to the buckets
        self.peak_bucket += self.pir * time_inc / 8.0
        if self.peak_bucket > self.pbs:
            self.peak_bucket = self.pbs
        self.committed_bucket += self.cir * time_inc / 8.0
        if self.committed_bucket > self.cbs:
            self.committed_bucket = self.cbs

        if self.peak_bucket - packet.size < 0:
            packet.color = 'red'
        elif self.committed_bucket - packet.size < 0:
            packet.color = 'yellow'
            self.peak_bucket -= packet.size
        else:
            packet.color = 'green'
            self.peak_bucket -= packet.size
            self.committed_bucket -= packet.size

        self.out.put(packet)
