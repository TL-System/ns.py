"""
The TCP CUBIC congestion control algorithm, used in the Linux kernel since 2.6.19.

Reference:

Sangtae Ha; Injong Rhee; Lisong Xu. "CUBIC: A New TCP-Friendly High-Speed TCP Variant,"
ACM SIGOPS Operating Systems Review. 42 (5): 64–74, July 2008.
"""
from ns.flow.cc import CongestionControl


class TCPCubic(CongestionControl):
    """
        The TCP CUBIC congestion control algorithm, used in the Linux kernel since 2.6.19.

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
        super().__init__(mss, cwnd, ssthresh, debug)
        self.W_last_max: float = 0
        self.epoch_start = 0
        self.origin_point = 0
        self.d_min: float = 0
        self.W_tcp = 0
        self.K = 0
        self.ack_cnt = 0
        self.tcp_friendliness = True
        self.fast_convergence = True
        self.beta = 0.2
        self.C = 0.4
        self.cwnd_cnt = 0
        self.cnt = 0

    def __repr__(self):
        return f"cwnd: {self.cwnd}, ssthresh: {self.ssthresh}"

    def cubic_reset(self):
        """ Resetting the states in CUBIC. """
        self.W_last_max = 0
        self.epoch_start = 0
        self.origin_point = 0
        self.d_min = 0
        self.W_tcp = 0
        self.K = 0
        self.ack_cnt = 0

    def cubic_update(self, current_time):
        """ Updating CUBIC parameters upon the arrival of a new ack. """
        self.ack_cnt += 1
        if self.epoch_start <= 0:
            self.epoch_start = current_time
            if self.cwnd < self.W_last_max:
                self.K = ((self.W_last_max - self.cwnd) / self.C)**(1. / 3)
            else:
                self.K = 0
                self.origin_point = self.cwnd
            self.ack_cnt = 1
            self.W_tcp = self.cwnd
        t = current_time + self.d_min - self.epoch_start
        target = self.origin_point + self.C * (t - self.K)**3
        if target > self.cwnd:
            self.cnt = self.cwnd / (target - self.cwnd)
        else:
            self.cnt = 100 * self.cwnd
        if self.tcp_friendliness:
            self.cubic_tcp_friendliness()

    def cubic_tcp_friendliness(self):
        """ CUBIC actions in TCP mode. """
        self.W_tcp += 3 * self.beta / (2 - self.beta) * (self.ack_cnt /
                                                         self.cwnd)
        self.ack_cnt = 0
        if self.W_tcp > self.cwnd:
            max_cnt = self.cwnd / (self.W_tcp - self.cwnd)
            if self.cnt > max_cnt:
                self.cnt = max_cnt

    def timer_expired(self):
        """ Actions to be taken when a timer expired. """
        # setting the congestion window to 1 segment
        self.cwnd = self.mss
        self.cubic_reset()

    def ack_received(self, rtt: float = 0, current_time: float = 0):
        """ Actions to be taken when a new ack has been received. """
        if self.d_min > 0:
            self.d_min = min(self.d_min, rtt)
        else:
            self.d_min = rtt

        if self.cwnd <= self.ssthresh:
            # slow start
            self.cwnd += self.mss
        else:
            # congestion avoidance
            self.cubic_update(current_time)

            if self.cwnd_cnt > self.cnt:
                self.cwnd += self.mss
                self.cwnd_cnt = 0
            else:
                self.cwnd_cnt += 1
