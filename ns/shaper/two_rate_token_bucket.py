"""
Implements a FIFO two-rate shaper with committed and peak token buckets.
"""

import math

import simpy

from ns.utils.retained_store import remove_packet


class TwoRateTokenBucketShaper:
    """Shape FIFO traffic at PIR and describe eligibility at service start.

    Both byte buckets begin full and refill continuously at their bit/s rates.
    With PIR configured, peak tokens alone gate departure: green fits both
    buckets, yellow fits only peak, and red requires a peak wait. Only green uses
    committed tokens; yellow/red preserve that credit. Colors describe the head
    packet before its wait, rather than RFC 2698 arrival metering. With PIR absent,
    CIR gates departure and a packet that needs to wait is yellow.

    A packet larger than its gating bucket borrows the deficit by waiting at
    that rate, then leaves zero credit. This preserves large-packet compatibility
    but relaxes the burst envelope for that packet. For ordinary packet sizes,
    all traffic obeys PIR/PBS (or CIR/CBS with no PIR), and green traffic obeys
    CIR/CBS. Idle refill is capped; waits refill the other bucket as well.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    cir: int
        The positive Committed Information Rate (CIR) in bits/second.
    cbs: int
        The Committed Burst Size (CBS) in bytes.
    pir: int
        The optional positive Peak Information Rate (PIR) in bits/second, >= CIR.
    pbs: int
        The positive Peak Burst Size (PBS) in bytes, required with PIR.
    zero_buffer: bool
        Does this server have a zero-length buffer? This is useful when multiple
        basic elements need to be put together to construct a more complex element
        with a unified buffer.
    zero_downstream_buffer: bool
        Does this server's downstream element has a zero-length buffer? If so, packets
        may queue up in this element's own buffer rather than be forwarded to the
        next-hop element.
    debug: bool
        If True, prints more verbose debug information.
    """

    def __init__(
        self,
        env,
        cir,
        cbs,
        pir=None,
        pbs=None,
        zero_buffer=False,
        zero_downstream_buffer=False,
        debug=False,
    ):
        if (
            not math.isfinite(cir) or cir <= 0
            or not math.isfinite(cbs) or cbs <= 0
            or (pir is None) != (pbs is None)
            or pir is not None and (
                not math.isfinite(pir) or pir < cir
                or not math.isfinite(pbs) or pbs <= 0
            )
        ):
            raise ValueError(
                "Require finite CIR/CBS > 0 and optional PIR >= CIR, PBS > 0"
            )
        self.store = simpy.Store(env)
        self.env = env
        self.out = None
        self.cir = cir
        self.cbs = cbs
        self.pir = pir
        self.pbs = pbs
        self.packets_received = 0
        self.packets_sent = 0

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = simpy.Store(env)

        self.current_bucket_commit = cbs  # Current committed credit in bytes
        self.current_bucket_peak = pbs  # Current size of the peak bucket in bytes
        self.update_time = env.now  # Buckets start full when constructed.
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.action = env.process(self.run())

    def update(self, packet):
        """Release upstream ownership after local or downstream completion.

        A downstream zero-buffer consumer calls this after removing the packet
        from our retained store; otherwise run() releases at local completion.
        Direct input without upstream ownership needs no callback.
        """
        if self.zero_buffer and packet in self.upstream_stores:
            # Shared ownership must follow downstream selection, not FIFO order.
            store = self.upstream_stores.pop(packet)
            callback = self.upstream_updates.pop(packet)
            remove_packet(store, packet)
            callback(packet)

    def run(self):
        """Wait for FIFO work and missing gating tokens; colors precede waits."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_stores.get()
            else:
                packet = yield self.store.get()

            self.busy = 1
            now = self.env.now

            # Rates are bits/s; divide by 8 to refill byte-denominated buckets.
            self.current_bucket_commit = min(
                self.cbs,
                self.current_bucket_commit + self.cir * (now - self.update_time) / 8.0,
            )
            if self.pir is not None:
                self.current_bucket_peak = min(
                    self.pbs,
                    self.current_bucket_peak
                    + self.pir * (now - self.update_time) / 8.0,
                )
            self.update_time = now

            # Eligibility is assessed now; a wait preserves its initial color.
            # The gating bucket may borrow for a packet larger than capacity.
            if self.pir is not None:
                if packet.size > self.current_bucket_peak:
                    yield self.env.timeout(
                        (packet.size - self.current_bucket_peak) * 8.0 / self.pir
                    )
                    # Peak refill was entirely consumed by this packet. The
                    # committed bucket still accrues tokens throughout the wait.
                    self.current_bucket_commit = min(
                        self.cbs,
                        self.current_bucket_commit
                        + self.cir * (self.env.now - self.update_time) / 8.0,
                    )
                    self.current_bucket_peak = 0.0
                    packet.color = "red"
                elif packet.size > self.current_bucket_commit:
                    self.current_bucket_peak -= packet.size
                    packet.color = "yellow"
                else:
                    self.current_bucket_commit -= packet.size
                    self.current_bucket_peak -= packet.size
                    packet.color = "green"

            else:  # With no peak bucket, CIR itself gates all departures.
                if packet.size > self.current_bucket_commit:
                    yield self.env.timeout(
                        (packet.size - self.current_bucket_commit) * 8.0 / self.cir
                    )
                    self.current_bucket_commit = 0.0
                    packet.color = "yellow"
                else:
                    self.current_bucket_commit -= packet.size
                    packet.color = "green"
            self.update_time = self.env.now

            # A synchronous downstream callback should observe finished service.
            self.busy = 0
            if self.zero_downstream_buffer:
                self.out.put(
                    packet, upstream_update=self.update, upstream_store=self.store
                )
            else:
                self.update(packet)
                self.out.put(packet)

            self.packets_sent += 1
            if self.debug:
                print(
                    f"Sent out packet with id {packet.packet_id} "
                    f"belonging to flow {packet.flow_id} with color {packet.color}."
                )

    def put(self, packet, upstream_update=None, upstream_store=None):
        """Sends a packet to this element."""
        self.packets_received += 1
        if (
            self.zero_buffer
            and upstream_update is not None
            and upstream_store is not None
        ):
            self.upstream_stores[packet] = upstream_store
            self.upstream_updates[packet] = upstream_update

        if self.zero_downstream_buffer:
            self.downstream_stores.put(packet)
        return self.store.put(packet)
