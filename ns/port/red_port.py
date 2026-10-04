"""Random Early Detection over the port's resident packet/byte occupancy."""

import math
import random

from ns.port.port import Port


class REDPort(Port):
    """A FIFO port with arrival-sampled RED and ordinary hard capacity admission.

    ``rate`` is bits/second (zero means unlimited); ``qlimit`` is a resident
    byte/packet capacity, including service and downstream retention. None is
    unlimited, zero admits nothing, and an exact fit is accepted, as in Port.

    On every arrival, including capacity drops, sample occupancy *before* the
    arriving packet and update the EWMA with alpha = 2**(-weight_factor).
    At/below min_threshold no packet is dropped; in the open threshold interval
    drop with linearly increasing probability, and at/above max_threshold drop
    unconditionally. max_probability is the probability approached from below.
    Thresholds use the same byte/packet unit as qlimit.

    The simplified model updates only on arrivals: elapsed idle time itself does
    not decay the average. This matches current Days' arrival recurrence, but
    Days samples waiting slots and uses a deterministic counter. Here we retain
    Port's resident accounting and independent random draws, with no RED count
    correction or ECN marking. Tests inject explicit draws instead of equating
    random seeds across simulators.
    """

    def __init__(
        self,
        env,
        rate: float,
        max_threshold: int,
        min_threshold: int,
        max_probability: float,
        weight_factor: int = 9,
        element_id: int = None,
        qlimit: int = None,
        limit_bytes: bool = False,
        zero_downstream_buffer: bool = False,
        debug: bool = False,
    ):
        if (
            not all(math.isfinite(value) for value in (
                rate, min_threshold, max_threshold, max_probability, weight_factor
            ))
            or rate < 0
            or not 0 <= min_threshold < max_threshold
            or not 0 <= max_probability <= 1
            or weight_factor < 0
            or qlimit is not None and (not math.isfinite(qlimit) or qlimit < 0)
        ):
            raise ValueError(
                "Invalid RED rate, thresholds, probability, weight or capacity"
            )
        super().__init__(
            env, rate, element_id=element_id, qlimit=qlimit,
            limit_bytes=limit_bytes, zero_downstream_buffer=zero_downstream_buffer,
            debug=debug,
        )
        self.max_probability = max_probability
        self.max_threshold = max_threshold
        self.min_threshold = min_threshold
        self.weight_factor = weight_factor
        self.average_queue_size = 0

    def put(self, packet):
        """Sample residents, then decide admission exactly once for this arrival."""
        resident_packets = (
            self.packets_received - self.packets_dropped - self._packets_removed
        )
        sample = self.byte_size if self.limit_bytes else resident_packets
        alpha = 2**-self.weight_factor
        self.average_queue_size = (1 - alpha) * self.average_queue_size + alpha * sample

        # Hard capacity comes first, so overflow never consumes a random draw.
        # Delegate admission/accounting to Port rather than maintaining a second
        # implementation that forgets service or retained downstream ownership.
        post_depth = sample + (packet.size if self.limit_bytes else 1)
        if self.qlimit is not None and post_depth > self.qlimit:
            return super().put(packet)

        average = self.average_queue_size
        drop = average >= self.max_threshold
        if self.min_threshold < average < self.max_threshold:
            probability = self.max_probability * (
                (average - self.min_threshold)
                / (self.max_threshold - self.min_threshold)
            )
            # Strict comparison gives probability zero no drops, even for draw 0.
            drop = random.uniform(0, 1) < probability
        if drop:
            self.packets_received += 1
            self.packets_dropped += 1
            if self.element_id is not None:
                packet.perhop_time[self.element_id] = self.env.now
            if self.debug:
                print(f"RED dropped packet {packet.packet_id}: average {average}")
            return None
        return super().put(packet)
