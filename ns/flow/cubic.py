"""
TCP CUBIC congestion control (RFC 8312) as used in Linux since v2.6.19.

Reference: Sangtae Ha, Injong Rhee, Lisong Xu. "CUBIC: A New TCP-Friendly
High-Speed TCP Variant," ACM SIGOPS OSR, 42(5):64–74, 2008.
"""
from __future__ import annotations

from ns.flow.cc import LossBasedCongestionControl


class TCPCubic(LossBasedCongestionControl):
    """
    TCP CUBIC congestion control with RFC 8312 compliant window update rules.

    Parameters
    ----------
    mss: int
        The maximum segment size (bytes).
    cwnd: int
        The initial congestion window (bytes).
    ssthresh: int
        Initial slow-start threshold (bytes).
    beta: float
        Multiplicative decrease factor (default 0.2 per RFC 8312 §4.6).
    cubic_constant: float
        C in the cubic function W(t) = C(t-K)^3 + W_max (default 0.4).
    debug: bool
        If True, prints more verbose debug information.
    """

    def __init__(
        self,
        mss: int = 512,
        cwnd: int = 512,
        ssthresh: int = 65535,
        beta: float = 0.2,
        cubic_constant: float = 0.4,
        debug: bool = False,
    ):
        super().__init__(mss, cwnd, ssthresh, debug)
        self.beta = beta
        self.beta_timeout = beta  # RFC 8312 uses the same decrease on RTO.
        self.cubic_c = cubic_constant

        # Internal state is tracked in packets (segments) to mirror RFC notation.
        self.W_last_max: float = 0.0
        self.epoch_start = 0.0
        self.origin_point = 0.0
        self.d_min: float = 0.0
        self.W_tcp = self.cwnd_in_segments()
        self.K = 0.0
        self.ack_cnt = 0.0
        self.tcp_friendliness = True
        self.fast_convergence = True
        self.cwnd_cnt = 0.0
        self.cnt = float("inf")

    def __repr__(self):
        return f"cwnd: {self.cwnd}, ssthresh: {self.ssthresh}"

    def ack_received(self, rtt: float = 0, current_time: float = 0):
        """Record the minimum RTT and defer to LossBased's slow start logic."""
        if rtt > 0:
            self.d_min = rtt if self.d_min == 0 else min(self.d_min, rtt)
        super().ack_received(rtt, current_time)

    def _congestion_avoidance_ack(self, rtt: float, current_time: float):
        # Without an RTT sample we fall back to Reno-style additive increase.
        if self.d_min <= 0:
            self.cwnd += (self.mss * self.mss) / self.cwnd
            return

        self.cubic_update(current_time)
        ack_threshold = max(1.0, self.cnt)
        self.cwnd_cnt += 1
        if self.cwnd_cnt >= ack_threshold:
            self.cwnd += self.mss
            self.cwnd_cnt = 0

    def cubic_update(self, current_time: float):
        """Update the cubic window target (RFC 8312 §4.1)."""
        cwnd_packets = self.cwnd_in_segments()
        self.ack_cnt += 1

        if self.epoch_start <= 0:
            self.epoch_start = current_time
            self.ack_cnt = 1
            if cwnd_packets < self.W_last_max:
                self.K = ((self.W_last_max - cwnd_packets) / self.cubic_c) ** (1.0 / 3.0)
                self.origin_point = self.W_last_max
            else:
                self.K = 0.0
                self.W_last_max = cwnd_packets
                self.origin_point = cwnd_packets
            self.W_tcp = cwnd_packets

        t = current_time + self.d_min - self.epoch_start
        target = self.origin_point + self.cubic_c * (t - self.K) ** 3
        if target > cwnd_packets:
            self.cnt = cwnd_packets / max(target - cwnd_packets, 1e-6)
        else:
            self.cnt = 100.0 * max(1.0, cwnd_packets)

        if self.tcp_friendliness:
            self.cubic_tcp_friendliness(cwnd_packets)

    def cubic_tcp_friendliness(self, cwnd_packets: float):
        """TCP-friendly mode keeps pace with Reno while probing above W_max."""
        if cwnd_packets <= 0:
            return
        self.W_tcp += 3 * self.beta / (2 - self.beta) * (self.ack_cnt / cwnd_packets)
        self.ack_cnt = 0
        if self.W_tcp > cwnd_packets:
            max_cnt = cwnd_packets / max(self.W_tcp - cwnd_packets, 1e-6)
            self.cnt = min(self.cnt, max_cnt)

    def _reset_epoch(self):
        """Drop epoch-specific state so the next ACK starts a fresh cubic phase."""
        self.epoch_start = 0.0
        self.K = 0.0
        self.ack_cnt = 0.0
        self.cnt = float("inf")
        self.cwnd_cnt = 0.0
        self.W_tcp = self.cwnd_in_segments()

    def _after_fast_loss(self, prev_cwnd: float, packet=None):
        """RFC 8312 §4.6 fast convergence bookkeeping."""
        cwnd_packets = prev_cwnd / self.mss
        if self.fast_convergence and cwnd_packets < self.W_last_max:
            self.W_last_max = cwnd_packets * (1 + self.beta) / 2.0
        else:
            self.W_last_max = cwnd_packets
        self._reset_epoch()

    def _after_timeout(self, prev_cwnd: float, packet=None):
        """Timeouts force a new epoch but keep the most recent W_max."""
        del packet
        self.W_last_max = prev_cwnd / self.mss
        self._reset_epoch()
