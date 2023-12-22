""" A dataclass for keeping track of all the properties of a network flow. """

from dataclasses import dataclass
from collections.abc import Callable
from enum import Enum, auto


class AppType(Enum):
    BULK_TRANSFER = (auto(),)
    VIDEO = (auto(),)
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

    def __repr__(self) -> str:
        return f"Flow {self.fid} on {self.path}"

    def init_send_buffer(self):
        if self.typ == AppType.BULK_TRANSFER:
            return self.size
        else:
            return 0

    def next_send_buffer(self, current_time):
        if self.typ == AppType.BULK_TRANSFER:
            return 0
        new_packet = 0
        arrival_wait = self.arrival_dist()

        while current_time - self.last_arrival > arrival_wait:
            new_packet += self.size_dist()
            self.last_arrival += arrival_wait
            arrival_wait = self.arrival_dist()

        return new_packet
