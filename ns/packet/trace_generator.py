"""Replay a whitespace-delimited packet trace in file order."""

import math
from collections.abc import Generator, Hashable
from os import PathLike
from typing import Any

import simpy

from ns.packet.packet import Packet


class TracePacketGenerator:
    """Replay ``flow_id packet_id time size`` or, with flow_id, ``id time size``.

    Trace times are nondecreasing seconds relative to generation start; sizes
    are nonnegative bytes. Equal timestamps preserve file order. ``initial_delay``
    offsets every timestamp; ``finish`` is an absolute, exclusive stop time.
    """

    def __init__(
        self,
        env: simpy.Environment,
        element_id: Hashable,
        filename: str | PathLike[str],
        initial_delay: float = 0,
        finish: float = float("inf"),
        flow_id: Hashable | None = None,
        rec_flow: bool = False,
        debug: bool = False,
    ) -> None:
        self.element_id = element_id
        self.env = env
        self.filename = filename
        self.initial_delay = initial_delay
        self.finish = finish
        if not math.isfinite(initial_delay) or initial_delay < 0:
            raise ValueError("initial_delay must be finite and nonnegative.")
        if math.isnan(finish) or finish < 0:
            raise ValueError("finish must be nonnegative.")
        self.out: Any = None
        self.flow_id = flow_id
        self.packets_sent = 0
        self.action = env.process(self.run())

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []

        self.debug = debug

    def run(self) -> Generator[simpy.Event, Any, None]:
        """Wait to each trace timestamp, stopping at finish or end of file."""
        start = self.env.now + self.initial_delay
        delay = min(self.initial_delay, max(0, self.finish - self.env.now))
        yield self.env.timeout(delay)
        if self.env.now >= self.finish:
            return
        last_packet_time = 0
        # Scope the file to replay, including early finish and parse failures.
        with open(self.filename) as trace:
            for line in trace:
                row = line.split()
                if self.flow_id is None:
                    trace_flow, packet_id, time, size = row
                    flow_id = int(trace_flow)
                else:
                    flow_id = self.flow_id
                    packet_id, time, size = row
                packet_id, time, size = int(packet_id), float(time), int(size)
                if not math.isfinite(time) or time < last_packet_time:
                    raise ValueError("trace times must be finite and nondecreasing.")
                if size < 0:
                    raise ValueError("trace packet size must be nonnegative.")

                arrival = start + time
                # Check before waiting so a row beyond finish cannot leak out.
                if arrival >= self.finish:
                    yield self.env.timeout(self.finish - self.env.now)
                    return
                yield self.env.timeout(arrival - self.env.now)
                last_packet_time = time

                self.packets_sent += 1
                packet = Packet(
                    self.env.now, size, packet_id, src=self.element_id, flow_id=flow_id
                )
                if self.rec_flow:
                    self.time_rec.append(packet.time)
                    self.size_rec.append(packet.size)

                if self.debug:
                    print(
                        f"Sent packet {packet.packet_id} with flow_id {packet.flow_id} "
                        f"at time {self.env.now}."
                    )

                self.out.put(packet)
