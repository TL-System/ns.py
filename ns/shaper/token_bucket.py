"""
Implements a token bucket shaper.
"""

import math
from collections.abc import Callable, Generator
from typing import Any

import simpy

from ns.packet.packet import Packet
from ns.utils.retained_store import remove_packet


class TokenBucketShaper:
    """Shape FIFO packets with an initially full byte token bucket.

    Positive finite rates are bits/second and capacities are positive finite
    bytes. For packets no larger than the bucket, token eligibility times obey
    the rate/burst envelope. Without peak serialization these are departures.
    With a peak rate, tokens gate serialization starts: completed packets may
    bunch when a small packet follows a large one. A conservative completion
    window bound adds (rate / peak) * max_packet_bytes to the burst allowance.
    Tokens accrue during peak service too, and idle refill is capped.

    An oversized packet borrows its deficit by waiting at the average rate, then
    leaves zero credit. This compatibility policy lets large packets through but
    cannot enforce the ordinary burst envelope for that packet.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    rate: int
        The positive token arrival rate in bits/second.
    bucket_size: int
        The token bucket size in bytes.
    peak: int (or None for an infinite peak sending rate)
        The positive peak sending rate in bits/second, or None for no service delay.
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
        env: simpy.Environment,
        rate: float,
        bucket_size: float,
        peak: float | None = None,
        zero_buffer: bool = False,
        zero_downstream_buffer: bool = False,
        debug: bool = False,
    ) -> None:
        if (
            not math.isfinite(rate) or rate <= 0
            or not math.isfinite(bucket_size) or bucket_size <= 0
            or peak is not None and (not math.isfinite(peak) or peak <= 0)
        ):
            raise ValueError(
                "Require positive finite rate, bucket size and optional peak"
            )
        self.store = simpy.Store(env)
        self.env = env
        self.rate = rate
        self.out: Any = None
        self.packets_received = 0
        self.packets_sent = 0
        self.bucket_size = bucket_size
        self.peak = peak

        self.upstream_updates = {}
        self.upstream_stores = {}
        self.zero_buffer = zero_buffer
        self.zero_downstream_buffer = zero_downstream_buffer
        if self.zero_downstream_buffer:
            self.downstream_stores = simpy.Store(env)

        self.current_bucket = bucket_size  # Current size of the bucket in bytes
        self.update_time = env.now  # A bucket starts full when constructed.
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent
        self.action = env.process(self.run())

    def update(self, packet: Packet) -> None:
        """Release upstream ownership after local or downstream completion.

        A downstream zero-buffer consumer calls this after removing the packet
        from our retained store; otherwise run() releases at local completion.
        Direct input without upstream ownership needs no callback.
        """
        if self.zero_buffer and packet in self.upstream_stores:
            # Downstream may reorder packets. Release this exact object and clear
            # hooks first, so callbacks can safely reenter or repeat the release.
            store = self.upstream_stores.pop(packet)
            callback = self.upstream_updates.pop(packet)
            remove_packet(store, packet)
            callback(packet)

        if self.debug:
            print(f"Sent packet {packet.packet_id} from flow {packet.flow_id}.")

    def run(self) -> Generator[simpy.Event, Any, None]:
        """Wait for FIFO work, missing byte tokens, and optional peak service."""
        while True:
            if self.zero_downstream_buffer:
                packet = yield self.downstream_stores.get()
            else:
                packet = yield self.store.get()

            self.busy = 1
            now = self.env.now

            # Convert bits/second to byte tokens; include idle and peak service.
            self.current_bucket = min(
                self.bucket_size,
                self.current_bucket + self.rate * (now - self.update_time) / 8.0,
            )
            self.update_time = now

            # Wait for the deficit even if size exceeds capacity: oversized
            # packets may borrow credit, but depart with an empty bucket.
            if packet.size > self.current_bucket:
                yield self.env.timeout(
                    (packet.size - self.current_bucket) * 8.0 / self.rate
                )
                self.current_bucket = 0.0
            else:
                self.current_bucket -= packet.size
            self.update_time = self.env.now

            if self.peak is not None:
                # Serialize byte-sized packets on the optional bits/s peak link.
                yield self.env.timeout(packet.size * 8.0 / self.peak)
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
                print(f"Sent packet {packet.packet_id} from flow {packet.flow_id}.")

    def put(
        self, packet: Packet,
        upstream_update: Callable[[Packet], None] | None = None,
        upstream_store: Any = None,
    ) -> simpy.Event:
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
