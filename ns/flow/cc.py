"""
The base class for congestion control algorithms, designed to supply the TCPPacketGenerator class
with congestion control decisions.
"""
from abc import abstractmethod


class CongestionControl:
    """
        The base class for congestion control algorithms, designed to supply the TCPPacketGenerator
        class with congestion control decisions.

        Parameters
        ----------
        mss: int
            the maximum segment size
        cwnd: int
            the size of the congestion window.
        ssthresh: int
            the slow start threshold.
        debug: bool
            If True, prints more verbose debug information.
    """
    def __init__(self,
                 mss: int = 512,
                 cwnd: int = 512,
                 ssthresh: int = 65535,
                 debug: bool = False):
        self.mss = mss
        self.cwnd: float = cwnd
        self.ssthresh = ssthresh
        self.debug = debug

    def __repr__(self):
        return f"cwnd: {self.cwnd}, ssthresh: {self.ssthresh}"

    @abstractmethod
    def ack_received(self, rtt: float = 0, current_time: float = 0):
        """ Actions to be taken when a new ack has been received. """

    def timer_expired(self):
        """ Actions to be taken when a timer expired. """
        # setting the congestion window to 1 segment
        self.cwnd = self.mss

    def dupack_over(self):
        """ Actions to be taken when a new ack is received after previous dupacks. """
        # RFC 2001 and TCP Reno
        self.cwnd = self.ssthresh

    def consecutive_dupacks_received(self):
        """ Actions to be taken when three consecutive dupacks are received. """
        # fast retransmit in RFC 2001 and TCP Reno
        self.ssthresh = max(2 * self.mss, self.cwnd / 2)
        self.cwnd = self.ssthresh + 3 * self.mss

    def more_dupacks_received(self):
        """ Actions to be taken when more than three consecutive dupacks are received. """
        # fast retransmit in RFC 2001 and TCP Reno
        self.cwnd += self.mss


class TCPReno(CongestionControl):
    """ TCP Reno, defined in RFC 2001. """
    def ack_received(self, rtt: float = 0, current_time: float = 0):
        """ Actions to be taken when a new ack has been received. """
        if self.cwnd <= self.ssthresh:
            # slow start
            self.cwnd += self.mss
        else:
            # congestion avoidance
            self.cwnd += self.mss * self.mss / self.cwnd
