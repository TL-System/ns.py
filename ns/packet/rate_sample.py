"""Byte-based delivery-rate sampling, following the Cheng/Cardwell draft.

Each ACK group chooses one send snapshot. The longer of send and ACK elapsed
seconds bounds its bytes/second estimate, resisting compressed ACK arrivals.
"""

from __future__ import annotations

from ns.packet.packet import Packet


class RateSample:
    """Mutable feedback for one ACK; connection totals survive group resets."""

    rtt: float  # A negative value marks an ACK group without a usable RTT.

    def __init__(self) -> None:
        self.prior_lost = 0
        self.begin_ack()

    def begin_ack(self) -> None:
        """Discard the previous ACK's timing and rate, including invalid samples."""
        self.delivery_rate = 0
        self.delivered: float = 0
        self.prior_delivered: float = 0
        self.prior_time: float | None = None
        self.newly_acked = 0
        self.interval = 0
        self.ack_elapsed = 0
        self.send_elapsed = 0
        self.rtt = -1
        self.is_app_limited = False
        self.newly_lost = 0
        self.lost = 0
        self.tx_in_flight = 0
        self._sample_sent_time: float | None = None

    def send_packet(
        self, packet: Packet, C: Connection,
        packets_in_flight: int, current_time: float,
    ) -> None:
        """Attach the latest attempt's snapshot without changing Packet.time."""
        if packets_in_flight == 0:
            # No earlier flight can supply a useful delivery/send clock.
            C.first_sent_time = C.delivered_time = current_time
        packet.sent_time = current_time
        packet.first_sent_time = C.first_sent_time
        packet.delivered_time = C.delivered_time
        packet.delivered = C.delivered
        packet.lost = C.lost
        packet.is_app_limited = bool(C.is_app_limited)

    def updaterate_sample(
        self, packet: Packet, C: Connection, current_time: float,
    ) -> None:
        """Credit an ACKed range once and retain the most recent send snapshot.

        The sender supplies only newly covered bytes, including partial ranges.
        None marks consumption; simulation time zero is a valid timestamp.
        """
        if packet.delivered_time is None:
            return
        C.delivered += packet.size
        C.delivered_time = current_time
        sent_time = packet.time if packet.sent_time is None else packet.sent_time
        if (self.prior_time is None or packet.delivered > self.prior_delivered
                or (packet.delivered == self.prior_delivered
                    and self._sample_sent_time is not None
                    and sent_time >= self._sample_sent_time)):
            self.prior_delivered = packet.delivered
            self.prior_time = packet.delivered_time
            self._sample_sent_time = sent_time
            self.send_elapsed = sent_time - packet.first_sent_time
            self.ack_elapsed = current_time - packet.delivered_time
            self.is_app_limited = packet.is_app_limited
            self.tx_in_flight = packet.tx_in_flight
            self.lost = C.lost - packet.lost
            C.first_sent_time = sent_time
        packet.delivered_time = None

    def update_sample_group(self, C: Connection, minRTT: float = -1) -> bool:
        """Finalize one group; unusable clocks never leave a stale rate behind."""
        self.delivery_rate = 0
        self.newly_lost = C.lost - self.prior_lost
        self.prior_lost = C.lost
        if C.is_app_limited and C.delivered > C.is_app_limited:
            C.is_app_limited = 0
        if self.prior_time is None:
            return False
        self.delivered = C.delivered - self.prior_delivered
        self.interval = max(self.ack_elapsed, self.send_elapsed)
        if self.delivered <= 0 or self.interval <= 0 or self.interval < minRTT:
            return False
        self.delivery_rate = self.delivered / self.interval
        return True


class Connection:
    """Cumulative byte counters and the application-limited delivery frontier."""

    def __init__(self) -> None:
        self.is_app_limited = 0
        self.first_sent_time: float = 0
        self.delivered: float = 0
        self.delivered_time: float = 0
        self.lost = 0
        self.lost_out = 0
        self.retrans_out = 0
        self.is_cwnd_limited = False
        self.write_seq = 0
        self.pending_trans = 0

    def mark_connection_app_limited(self, packets_in_flight: float) -> None:
        # Preserve the boundary through the entire application-limited flight;
        # zero means unmarked, so an empty connection uses the boundary one.
        self.is_app_limited = max(1, self.delivered + packets_in_flight)

    def check_if_application_limited(
        self, next_seq: int, mss: int, packet_in_flight: int,
    ) -> None:
        """Mark lack of one full segment, unless window or recovery blocks it.

        This transport has no lower-layer transmit queue or SACK loss ledger.
        pending_trans/lost_out/retrans_out retain the draft's useful conditions
        for callers that provide those estimates; all three count bytes.
        """
        if (self.write_seq - next_seq < mss and self.pending_trans == 0
                and not self.is_cwnd_limited and self.lost_out <= self.retrans_out):
            self.mark_connection_app_limited(packet_in_flight)
