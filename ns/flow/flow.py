"""A dataclass for keeping track of all the properties of a network flow."""

import math
from dataclasses import dataclass, field
from collections.abc import Callable
from enum import Enum, auto


class AppType(Enum):
    BULK_TRANSFER = auto()
    VIDEO = auto()
    GAME = auto()


@dataclass
class Flow:
    """A dataclass for keeping track of all the properties of a network flow."""

    fid: int  # flow id
    src: str  # source element
    dst: str  # destination element
    size: int = None  # flow size in bytes
    start_time: float = None
    finish_time: float = None
    arrival_dist: Callable = None  # packet arrival distribution
    size_dist: Callable = None  # packet size distribution
    pkt_gen: object = None
    pkt_sink: object = None
    path: list = None
    typ: AppType = AppType.BULK_TRANSFER
    last_arrival: float = 0
    _next_arrival: float | None = field(default=None, init=False, repr=False)
    _generated_bytes: float = field(default=0, init=False, repr=False)

    def __repr__(self) -> str:
        return f"Flow {self.fid} on {self.path}"

    def init_send_buffer(self):
        """Bulk data is ready immediately; streaming data arrives over time.

        ``None`` keeps the existing unlimited-bulk sentinel. Streaming helpers
        are optional; TCP/BBR senders maintain their own application clocks.
        """
        if self.typ == AppType.BULK_TRANSFER:
            return self.size
        else:
            return 0

    def next_send_buffer(self, current_time):
        """Return newly available streaming bytes through current_time.

        Retain the next arrival across polls, include arrivals exactly at the
        poll time, and exclude arrivals at finish_time. Positive intervals keep
        this synchronous catch-up loop advancing. A finite size caps total bytes.
        """
        if self.typ == AppType.BULK_TRANSFER:
            return 0
        limit = math.inf if self.size is None else self.size
        finish = math.inf if self.finish_time is None else self.finish_time
        new_bytes = 0
        while self._generated_bytes < limit:
            if self._next_arrival is None:
                interval = self.arrival_dist()
                if not math.isfinite(interval) or interval <= 0:
                    raise ValueError("application interval must be positive and finite.")
                anchor = max(self.last_arrival, self.start_time or 0)
                self._next_arrival = anchor + interval
                if self._next_arrival <= anchor:
                    raise ValueError("application interval does not advance time.")
            if self._next_arrival > current_time or self._next_arrival >= finish:
                break
            packet_size = self.size_dist()
            if not math.isfinite(packet_size) or packet_size < 0:
                raise ValueError("application size must be finite and nonnegative.")
            # Both quantities are bytes; a short final arrival exhausts the budget.
            packet_size = min(packet_size, limit - self._generated_bytes)
            new_bytes += packet_size
            self._generated_bytes += packet_size
            self.last_arrival = self._next_arrival
            self._next_arrival = None
        return new_bytes
