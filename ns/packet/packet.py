"""
A very simple class that represents a packet.
"""

from collections.abc import Hashable
from typing import Any


class Packet:
    """
    Packets in ns.py are generally created by packet generators, and will run
    through a queue at an output port.

    Key fields include: generation time, size, flow_id, packet id, source, and
    destination. The optional payload is opaque to link elements: the size
    (in bytes) field determines transmission time, irrespective of that payload.

    We use a float to represent the size of the packet in bytes so that we can
    compare to ideal M/M/1 queues.

    Parameters
    ----------
    time: float
        the time when the packet is generated. For TCP data packets, transport
        code treats this as the original first-transmit timestamp used by sinks
        for end-to-end latency accounting. Retransmit-attempt timing belongs to
        sender-owned state, not to later mutation of this field.
    size: float
        the size of the packet in bytes
    packet_id: int
        an identifier for the packet
    src, dst: int
        identifiers for the source and destination
    flow_id: int or str
        an integer or string that can be used to identify a flow
    """

    def __init__(
        self,
        time: float,
        size: float,
        packet_id: int,
        realtime: float = 0,
        last_ack_time: float = 0,
        delivered: int = -1,
        src: Hashable = "source",
        dst: Hashable = "destination",
        flow_id: Hashable = 0,
        payload: Any = None,
        tx_in_flight: int = -1,
    ) -> None:
        self.time = time
        self.delivered_time: float | None = last_ack_time
        self.first_sent_time: float = 0
        # Delivery sampling replaces this with the latest attempt's send time.
        self.sent_time: float | None = None
        self.size = size
        self.packet_id = packet_id
        self.realtime = realtime
        self.src = src
        self.dst = dst
        self.flow_id = flow_id
        self.payload = payload
        self.lost = 0
        self.self_lost = False
        self.tx_in_flight = tx_in_flight
        self.delivered: float
        if delivered == -1:
            self.delivered = packet_id
        else:
            self.delivered = delivered

        self.is_app_limited = False
        self.color = None  # String color used by two-rate shaping and TrTCM.
        self.prio = {}  # used by the Static Priority scheduler
        self.ack = None  # used by TCPPacketGenerator and TCPSink
        # Latest wire-entry time, retained as diagnostic metadata for compatibility.
        # Wire keeps its actual propagation clock locally so sharing this packet
        # across two paths cannot overwrite either path's timing state.
        self.current_time: float = 0
        self.perhop_time = {}  # per-port arrival times in simulation seconds

    def __repr__(self) -> str:
        return f"id: {self.packet_id}, src: {self.src}, time: {self.time}, size: {self.size}"
