"""
Shared congestion-control infrastructure for loss-based TCP variants.

The Simulator models cwnd in *bytes* so the helpers provided here enforce RFC 5681/8312
requirements while letting individual algorithms focus on their window update rules.
"""

from __future__ import annotations

from abc import abstractmethod
from enum import Enum, auto
from typing import Final


class LossEvent(Enum):
    """Enumerates the two canonical loss signals in TCP."""

    FAST_LOSS = auto()
    TIMEOUT = auto()


class CongestionControl:
    """
    Base class for congestion control algorithms, designed to supply TCPPacketGenerator
    with congestion-control decisions.

    Parameters
    ----------
    mss: int
        Maximum segment size in bytes.
    cwnd: int
        Congestion window in bytes.
    ssthresh: int
        Slow-start threshold in bytes.
    debug: bool
        If True, prints more verbose debug information.
    """

    def __init__(
        self,
        mss: int = 512,
        cwnd: int = 512,
        ssthresh: int = 65535,
        debug: bool = False,
    ):
        self.mss = mss
        self.cwnd: float = cwnd
        self.ssthresh = ssthresh
        self.debug = debug
        self.next_departure_time = 0
        self.pacing_rate = 0
        self.rs = None
        self.C = None

    def __repr__(self):
        return f"cwnd: {self.cwnd}, ssthresh: {self.ssthresh}"

    @abstractmethod
    def ack_received(self, rtt: float = 0, current_time: float = 0):
        """Actions to be taken when a new ack has been received."""

    def timer_expired(self, packet=None):
        """Actions to be taken when a timer expired."""
        raise NotImplementedError("timer_expired must be implemented by subclasses.")

    def dupack_over(self):
        """Actions to be taken when a new ack is received after previous dupacks."""
        raise NotImplementedError("dupack_over must be implemented by subclasses.")

    def consecutive_dupacks_received(self, packet=None):
        """Actions to be taken when three consecutive dupacks are received."""
        raise NotImplementedError(
            "consecutive_dupacks_received must be implemented by subclasses."
        )

    def more_dupacks_received(self, packet=None):
        """Actions to be taken when more than three consecutive dupacks are received."""
        raise NotImplementedError(
            "more_dupacks_received must be implemented by subclasses."
        )

    def cwnd_in_segments(self) -> float:
        """Return the congestion window expressed in number of MSS-sized segments."""
        return self.cwnd / self.mss

    def min_ssthresh(self) -> float:
        """The RFC 5681-compliant minimum slow-start threshold (2 MSS)."""
        return 2 * self.mss

    def set_before_control(self, current_time, packet_in_flight: int = 0):
        """Optional hook for controllers that need per-send context (used by BBR)."""
        _ = (current_time, packet_in_flight)


class LossBasedCongestionControl(CongestionControl):
    """
    Implements the shared bookkeeping for Reno-like algorithms that respond to loss.

    The derived classes must provide the congestion-avoidance rule via
    :meth:`_congestion_avoidance_ack` and may override the loss hooks if additional
    state (e.g., CUBIC's epoch) needs to be updated.
    """

    beta: Final[float] = 0.5
    beta_timeout: Final[float] = 0.5

    def ack_received(self, rtt: float = 0, current_time: float = 0):
        """RFC 5681 slow start followed by an algorithm-specific avoidance rule."""
        if self.cwnd < self.ssthresh:
            self._slow_start_ack()
        else:
            self._congestion_avoidance_ack(rtt, current_time)

    def timer_expired(self, packet=None):
        """RFC 5681 timeout handling."""
        prev_cwnd = self.cwnd
        self.ssthresh = self._ssthresh_after_loss(prev_cwnd, LossEvent.TIMEOUT)
        self.cwnd = self.mss  # reset to one MSS per RFC 5681 §3.1
        self._after_timeout(prev_cwnd, packet)

    def dupack_over(self):
        """Exit fast recovery once the lost data is cumulatively acknowledged."""
        self.cwnd = self.ssthresh
        self._after_fast_recovery_exit()

    def consecutive_dupacks_received(self, packet=None):
        """Standard fast retransmit / fast recovery entry."""
        prev_cwnd = self.cwnd
        self.ssthresh = self._ssthresh_after_loss(prev_cwnd, LossEvent.FAST_LOSS)
        # Per RFC 5681 §3.2, inflate the window by 3 segments to keep the ACK clock.
        self.cwnd = self.ssthresh + 3 * self.mss
        self._after_fast_loss(prev_cwnd, packet)

    def more_dupacks_received(self, packet=None):
        """Additional dupacks add one MSS so we clock out a replacement segment."""
        self.cwnd += self.mss
        self._during_fast_recovery(packet)

    def _slow_start_ack(self):
        self.cwnd += self.mss

    @abstractmethod
    def _congestion_avoidance_ack(self, rtt: float, current_time: float):
        """Algorithm-specific congestion avoidance (one cwnd increase per RTT)."""

    def _ssthresh_after_loss(self, prev_cwnd: float, event: LossEvent) -> float:
        factor = self.beta_timeout if event == LossEvent.TIMEOUT else self.beta
        target = prev_cwnd * (1 - factor)
        return max(self.min_ssthresh(), target)

    def _after_fast_loss(self, prev_cwnd: float, packet=None):
        """Hook for algorithms that maintain extra state on fast loss."""
        _ = (prev_cwnd, packet)

    def _during_fast_recovery(self, packet=None):
        """Hook invoked for each extra dupack while in fast recovery."""
        _ = packet

    def _after_fast_recovery_exit(self):
        """Hook invoked when fast recovery completes."""

    def _after_timeout(self, prev_cwnd: float, packet=None):
        """Hook invoked after the timeout logic resets cwnd."""
        _ = (prev_cwnd, packet)


class TCPReno(LossBasedCongestionControl):
    """TCP Reno as defined in RFC 5681."""

    def _congestion_avoidance_ack(self, rtt: float = 0, current_time: float = 0):
        """Additively increase cwnd by roughly one MSS per RTT."""
        del rtt, current_time
        self.cwnd += (self.mss * self.mss) / self.cwnd
