"""
Shared congestion-control infrastructure for loss-based TCP variants.

Windows, flight sizes, and ACK credit are bytes. The transport owns recovery
frontiers; controllers choose the window response to each feedback event.
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

    def ack_received_bytes(self, acknowledged_bytes, rtt, current_time):
        """Bridge byte feedback to controllers with the older two-argument API.

        ``rtt=None`` means no fresh transport sample; numeric zero is a valid
        zero-delay sample. Older controllers use zero for an unknown sample.
        """
        self.ack_received(0 if rtt is None else rtt, current_time)

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
        """Optional hook for controllers that need context before feedback."""
        _ = (current_time, packet_in_flight)

    def partial_ack_received(self, acknowledged_bytes: int, current_time: float):
        """Notify a partial recovery ACK without exiting or normal ACK growth.

        The transport retransmits the next missing range and retains its recovery
        frontier. Controllers may use newly acknowledged bytes to adjust the
        recovery window; this default leaves it unchanged.
        """
        _ = (acknowledged_bytes, current_time)


class LossBasedCongestionControl(CongestionControl):
    """
    Implements the shared bookkeeping for Reno-like algorithms that respond to loss.

    The derived classes must provide the congestion-avoidance rule via
    :meth:`_congestion_avoidance_ack` and may override the loss hooks if additional
    state (e.g., CUBIC's epoch) needs to be updated.
    """

    beta: Final[float] = 0.5
    beta_timeout: Final[float] = 0.5

    def __init__(self, mss=512, cwnd=512, ssthresh=65535, debug=False):
        super().__init__(mss, cwnd, ssthresh, debug)
        # Context is supplied before each transport feedback event. None means
        # a direct controller call without flight information; zero is real.
        self.flight_size = None
        self.current_time = 0
        self.ca_credit = 0  # acknowledged bytes toward Reno's next window increase

    def set_before_control(self, current_time, packet_in_flight: int = 0):
        """Record time in seconds and outstanding bytes before applying feedback."""
        self.current_time = current_time
        self.flight_size = packet_in_flight

    def ack_received_bytes(self, acknowledged_bytes, rtt, current_time):
        """Use the transport's exact newly acknowledged byte count."""
        self.ack_received(rtt, current_time, acknowledged_bytes)

    def ack_received(
        self, rtt: float | None = 0, current_time: float = 0,
        acknowledged_bytes: int | None = None,
    ):
        """Grow on new ACKs; direct calls without a byte count acknowledge one MSS."""
        if acknowledged_bytes is None:
            acknowledged_bytes = self.mss
        self.flight_size = None  # consumed context must not leak into direct calls
        if self.cwnd < self.ssthresh:
            self._slow_start_ack(acknowledged_bytes)
        else:
            self._congestion_avoidance_ack(rtt, current_time, acknowledged_bytes)

    def timer_expired(self, packet=None):
        """RFC 5681 timeout handling."""
        prev_cwnd = self.cwnd
        flight = prev_cwnd if self.flight_size is None else self.flight_size
        self.flight_size = None
        self.ssthresh = self._ssthresh_after_loss(flight, LossEvent.TIMEOUT)
        self.cwnd = self.mss  # reset to one MSS per RFC 5681 §3.1
        self.ca_credit = 0
        self._after_timeout(prev_cwnd, packet)

    def dupack_over(self):
        """Exit fast recovery once the lost data is cumulatively acknowledged."""
        self.cwnd = self.ssthresh
        self.flight_size = None
        self.ca_credit = 0
        self._after_fast_recovery_exit()

    def partial_ack_received(self, acknowledged_bytes: int, current_time: float):
        """Keep one segment of NewReno headroom for the next missing range."""
        self.flight_size = None
        self.cwnd = self.ssthresh + self.mss

    def consecutive_dupacks_received(self, packet=None):
        """Standard fast retransmit / fast recovery entry."""
        prev_cwnd = self.cwnd
        flight = prev_cwnd if self.flight_size is None else self.flight_size
        self.flight_size = None
        self.ssthresh = self._ssthresh_after_loss(flight, LossEvent.FAST_LOSS)
        # Per RFC 5681 §3.2, inflate the window by 3 segments to keep the ACK clock.
        self.cwnd = self.ssthresh + 3 * self.mss
        self.ca_credit = 0
        self._after_fast_loss(prev_cwnd, packet)

    def more_dupacks_received(self, packet=None):
        """Additional dupacks add one MSS so we clock out a replacement segment."""
        self.cwnd += self.mss
        self.flight_size = None
        self._during_fast_recovery(packet)

    def _slow_start_ack(self, acknowledged_bytes):
        # RFC 5681 byte counting limits each ACK to one MSS. Days clamps the
        # threshold crossing rather than carrying its overshoot into avoidance.
        self.cwnd = min(self.ssthresh, self.cwnd + min(self.mss, acknowledged_bytes))
        if self.cwnd == self.ssthresh:
            self.ca_credit = 0

    @abstractmethod
    def _congestion_avoidance_ack(
        self, rtt: float | None, current_time: float, acknowledged_bytes: int,
    ):
        """Algorithm-specific congestion avoidance (one cwnd increase per RTT)."""

    def _ssthresh_after_loss(self, flight_size: float, event: LossEvent) -> float:
        factor = self.beta_timeout if event == LossEvent.TIMEOUT else self.beta
        target = flight_size * (1 - factor)
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
    """Reno with byte-counted avoidance and transport-managed NewReno recovery."""

    def _congestion_avoidance_ack(self, rtt, current_time, acknowledged_bytes):
        """Add one MSS for each current window's worth of newly ACKed bytes."""
        del rtt, current_time
        self.ca_credit += acknowledged_bytes
        # Each increase raises the next window's cost. A cumulative ACK may
        # cover several windows; retain its unused byte credit for later ACKs.
        while self.ca_credit >= self.cwnd:
            self.ca_credit -= self.cwnd
            self.cwnd += self.mss
