"""Educational CUBIC matching the pinned Days CPU controller's equations.

Windows exposed to the transport are bytes; cubic curves use MSS-sized segments
and seconds. This is the Days model, not Linux CUBIC or full RFC 9438: it uses
segment-count slow start, a signed ACK step, and a simple elapsed-time friendly
estimate. See evidence/phase5_cubic.md for the reference and model differences.
"""

from __future__ import annotations

import math

from ns.flow.cc import LossBasedCongestionControl


class TCPCubic(LossBasedCongestionControl):
    """Cubic growth with fast convergence and a TCP-friendly estimate.

    ``mss``, ``cwnd``, and ``ssthresh`` are bytes. ``beta`` is the fraction
    **retained** after loss (default 0.7); ``cubic_constant`` is C (default 0.4).
    Earlier ns.py versions misleadingly called beta=0.2 RFC-compliant and used
    it as the fraction removed. Explicit beta arguments now have CUBIC's usual
    retained-fraction meaning. Constructor argument positions stay unchanged.
    """

    # Days bounds its fixed-point state here; keep the same segment ceiling
    # without importing its integer arithmetic into the educational model.
    max_window_segments = 2_000_000

    def __init__(
        self,
        mss: int = 512,
        cwnd: int = 512,
        ssthresh: int = 65535,
        beta: float = 0.7,
        cubic_constant: float = 0.4,
        debug: bool = False,
    ) -> None:
        super().__init__(mss, cwnd, ssthresh, debug)
        if not 0 < beta < 1:
            raise ValueError("beta must be a retained fraction between zero and one")
        if not math.isfinite(cubic_constant) or cubic_constant <= 0:
            raise ValueError("cubic_constant must be finite and positive")
        self.beta = beta
        self.cubic_c = cubic_constant
        self.fast_convergence = True
        self.tcp_friendliness = True

        # W_last_max is the last observed loss window; W_max is the possibly
        # smaller curve origin chosen by fast convergence. Both are segments.
        self.W_last_max = 0.0
        self.W_max = 0.0
        self.K = 0.0
        self.epoch_start: float | None = None  # zero is a valid simulation time
        self.srtt = 0.0
        self._in_slow_start = cwnd < ssthresh
        self._in_fast_recovery = False

    def ack_received(
        self,
        rtt: float | None = 0,
        current_time: float = 0,
        acknowledged_bytes: int | None = None,
    ) -> None:
        """Consume one advancing ACK; an omitted byte count means one MSS.

        None means Karn's rule supplied no fresh RTT sample. A measured zero
        RTT is valid; the controller floors it at 1 ns, as Days does. This
        numerical guard does not quantize the floating-point simulator clock.
        """
        self.flight_size = None
        if rtt is not None:
            sample = max(rtt, 1e-9)
            self.srtt = sample if self.srtt == 0 else (7 * self.srtt + sample) / 8
        acknowledged = self.mss if acknowledged_bytes is None else acknowledged_bytes
        if acknowledged <= 0 or self._in_fast_recovery:
            return
        if self._in_slow_start:
            # Days counts a short segment as one, and a cumulative ACK as the
            # ceiling of ACKed bytes/MSS; this differs from Reno byte counting.
            segments = (acknowledged + self.mss - 1) // self.mss
            self.cwnd = min(
                self.cwnd + segments * self.mss, self.max_window_segments * self.mss
            )
            if self.cwnd >= self.ssthresh:
                self._in_slow_start = False
                self.epoch_start = current_time
                if self.W_max == 0:
                    self.W_max = self.cwnd_in_segments()
                    self.K = 0.0
        else:
            self.cubic_update(current_time)

    def _congestion_avoidance_ack(
        self, rtt: float | None, current_time: float, acknowledged_bytes: int,
    ) -> None:
        """Satisfy the loss-based hook used by the shared controller interface."""
        _ = (rtt, acknowledged_bytes)
        self.cubic_update(current_time)

    def cubic_update(self, current_time: float) -> None:
        """Apply the Days cubic/friendly rule once per advancing ACK."""
        if self.epoch_start is None:
            self.epoch_start = current_time
            if self.W_max == 0:
                self.W_max = self.cwnd_in_segments()
                self.K = 0.0  # a first no-loss epoch starts at its current window
            else:
                self.K = math.cbrt(self.W_max * (1 - self.beta) / self.cubic_c)
        elapsed = max(0.0, current_time - self.epoch_start)
        rtt = max(self.srtt, 1e-9)
        friendly = self.beta * self.W_max
        friendly += 3 * (1 - self.beta) / (1 + self.beta) * elapsed / rtt
        # Bound both curves before choosing a region, as Days does. If both
        # saturate they are equal, so the signed cubic ACK step still applies.
        friendly = min(max(friendly, 1.0), self.max_window_segments)
        if self.tcp_friendliness and self._cubic_window(elapsed) < friendly:
            window = friendly
        else:
            window = self.cwnd_in_segments()
            target = self._cubic_window(elapsed + rtt)
            # In segments: delta=(target-window)/window. Unlike an ACK counter,
            # this preserves fractional credit and can move down toward target.
            window += (target - window) / max(window, 1.0)
        self.cwnd = min(max(window, 1.0), self.max_window_segments) * self.mss

    def _cubic_window(self, elapsed: float) -> float:
        # K^3=Wmax*(1-beta)/C makes W(0)=beta*Wmax after loss. Express that
        # boundary directly so cube-root rounding cannot change region choice.
        if elapsed == 0 and self.K > 0:
            window = self.beta * self.W_max
        else:
            window = self.W_max + self.cubic_c * (elapsed - self.K) ** 3
        return min(max(window, 1.0), self.max_window_segments)

    def consecutive_dupacks_received(self, packet: object | None = None) -> None:
        """Enter recovery using actual flight for reduction, cwnd for maxima."""
        current = self.cwnd_in_segments()
        if self.fast_convergence and current < self.W_last_max:
            self.W_max = current * (1 + self.beta) / 2
        else:
            self.W_max = current
        self.W_last_max = current
        flight = self.cwnd if self.flight_size is None else self.flight_size
        reduced = max(self.mss, self.beta * flight)
        self.ssthresh = max(2 * self.mss, reduced)
        self.cwnd = min(reduced, self.max_window_segments * self.mss)
        self.epoch_start = self.current_time
        self.K = math.cbrt(self.W_max * (1 - self.beta) / self.cubic_c)
        self._in_fast_recovery = True
        self._in_slow_start = False
        self.flight_size = None

    def more_dupacks_received(self, packet: object | None = None) -> None:
        """An extra recovery ACK permits one more segment of window."""
        if self._in_fast_recovery:
            self.cwnd = min(self.cwnd + self.mss, self.max_window_segments * self.mss)
        self.flight_size = None

    def partial_ack_received(
        self, acknowledged_bytes: int, current_time: float
    ) -> None:
        """Hold CUBIC's recovery window while transport retransmits the next hole.

        Phase 4's conservative recovery hook supplies no RTT measurement; SRTT
        stays unchanged here and on recovery exit, unlike Days echoed samples.
        """
        self.flight_size = None

    def dupack_over(self) -> None:
        """Deflate to threshold without moving the loss-time epoch."""
        self.cwnd = min(self.ssthresh, self.max_window_segments * self.mss)
        self._in_fast_recovery = False
        self._in_slow_start = False
        self.flight_size = None

    def timer_expired(self, packet: object | None = None) -> None:
        """Restart slow start and erase the old curve; retain the RTT estimate."""
        flight = self.cwnd if self.flight_size is None else self.flight_size
        self.ssthresh = min(
            max(2 * self.mss, self.beta * flight), self.max_window_segments * self.mss
        )
        self.cwnd = self.mss
        self.W_max = self.W_last_max = self.K = 0.0
        self.epoch_start = None
        self._in_slow_start = True
        self._in_fast_recovery = False
        self.flight_size = None
