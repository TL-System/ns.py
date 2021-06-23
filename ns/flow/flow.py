""" A dataclass for keeping track of all the properties of a network flow. """

from dataclasses import dataclass
from collections.abc import Callable


@dataclass
class Flow:
    """ A dataclass for keeping track of all the properties of a network flow. """
    fid: int  # flow id
    arrival_dist: Callable  # packet arrival distribution
    size_dist: Callable = None  # packet size distribution
    src: str = None  # source element
    dst: str = None  # destination element
    size: int = None  # flow size in bytes
    start_time: float = None
    finish_time: float = None
    pkt_gen: object = None
    pkt_sink: object = None
    path: list = None

    def __repr__(self) -> str:
        return f"Flow {self.fid} on {self.path}"
