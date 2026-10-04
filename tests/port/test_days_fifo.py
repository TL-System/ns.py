"""Compare ns.py with checked-in observations from actual Days CPU execution."""

import json
from pathlib import Path

import pytest
import simpy

from ns.packet.packet import Packet
from ns.packet.sink import PacketSink
from ns.port.port import Port
from ns.port.wire import Wire


FIXTURE = Path(__file__).resolve().parents[1] / "reference" / "days_fifo.json"
NS_PER_SECOND = 1_000_000_000
# Floating-point accumulation only: 1 fs, far below Days' 1 ns time quantum.
FLOAT_ERROR_NS = 0.000001


class DepartureRecorder:
    def __init__(self, env, downstream):
        self.env = env
        self.downstream = downstream
        self.records = []

    def put(self, packet):
        self.records.append((packet.packet_id, self.env.now * NS_PER_SECOND))
        return self.downstream.put(packet)


class IdentitySink(PacketSink):
    def __init__(self, env):
        super().__init__(env)
        self.records = []
        self.packets = []

    def put(self, packet):
        self.records.append((packet.packet_id, self.env.now * NS_PER_SECOND))
        self.packets.append(packet)
        super().put(packet)


def assert_observations(actual, expected):
    """Compare selection identity before timing, without global trace ordering."""
    assert [identity for identity, _ in actual] == [
        record["packet_id"] for record in expected
    ]
    assert [time for _, time in actual] == pytest.approx(
        [record["time_ns"] for record in expected], rel=0, abs=FLOAT_ERROR_NS
    )


def test_days_cpu_fixture_matches_hand_calculated_fifo():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    reference = fixture["reference"]
    assert reference["revision"] == "9ff20eac16dcdf752510b05cbcf526684dc05146"
    assert reference["backend"] == "cpu"
    assert reference["workers"] == 2
    assert reference["observation_mode"] == "full"
    assert reference["scalar_equal"] is True

    # At 8 Gbit/s, 8 * bytes / rate gives exactly 1 ns per byte. The final
    # packet arrives to an idle port at 5000 ns, then takes another 125 ns.
    assert fixture["output"]["departures"] == [
        {"packet_id": 0, "time_ns": 1000},
        {"packet_id": 3, "time_ns": 1500},
        {"packet_id": 6, "time_ns": 1750},
        {"packet_id": 9, "time_ns": 2500},
        {"packet_id": 12, "time_ns": 5125},
    ]
    delivered = [
        arrival for arrival in fixture["output"]["arrivals"]
        if arrival["disposition"] == "delivered"
    ]
    assert [record["time_ns"] for record in delivered] == [
        1100, 1600, 1850, 2600, 5225
    ]
    assert fixture["input"]["stop_time_ns"] == delivered[-1]["time_ns"]
    assert fixture["output"]["pending_events"] == 0
    assert fixture["output"]["resident_packets"] == 0


def test_fifo_port_and_wire_match_days_cpu_observations():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    inputs, expected = fixture["input"], fixture["output"]
    env = simpy.Environment()
    # Days capacity 0 means unlimited waiting packets; ns.py qlimit=None is
    # unlimited including service. This fixture exercises no admission limit.
    assert inputs["queue_capacity_packets"] == 0
    port = Port(env, rate=inputs["rate_bps"], qlimit=None, element_id=1)
    wire = Wire(env, delay_dist=lambda: inputs["propagation_ns"] / NS_PER_SECOND)
    sink = IdentitySink(env)
    recorder = DepartureRecorder(env, wire)
    port.out = recorder
    wire.out = sink
    packets = [
        Packet(
            time=record["arrival_ns"] / NS_PER_SECOND,
            size=record["size_bytes"],
            packet_id=record["packet_id"],
            flow_id=inputs["flow_id"],
        )
        for record in inputs["packets"]
    ]

    def arrivals():
        """Inject the explicit ordered arrivals, waiting only between timestamps."""
        previous_ns = 0
        for record, packet in zip(inputs["packets"], packets, strict=True):
            yield env.timeout((record["arrival_ns"] - previous_ns) / NS_PER_SECOND)
            port.put(packet)
            previous_ns = record["arrival_ns"]

    env.process(arrivals())
    # Days includes stop_time_ns. Fully drain this finite scenario so the final
    # delivery at exactly that time is observed despite SimPy's exclusive
    # numeric run(until=t). There are no emissions after the cutoff.
    env.run()
    assert env.now * NS_PER_SECOND == pytest.approx(
        inputs["stop_time_ns"], rel=0, abs=FLOAT_ERROR_NS
    )

    assert_observations(recorder.records, expected["departures"])
    deliveries = [
        arrival for arrival in expected["arrivals"]
        if arrival["disposition"] == "delivered"
    ]
    assert_observations(sink.records, deliveries)
    summary = expected["summary"]
    assert port.packets_received == summary["admitted_packets"] == len(packets)
    assert port.packets_dropped == summary["dropped_packets"] == 0
    assert port.byte_size == 0
    assert port.busy == 0
    assert not port.store.items
    assert sink.packets_received[0] == summary["received_packets"]
    assert sink.bytes_received[0] == summary["received_bytes"] == 2625
    assert sink.packets == packets  # The same objects arrive exactly once.
    assert sink.arrivals[0] == pytest.approx(
        [record["time_ns"] / NS_PER_SECOND for record in deliveries],
        rel=0,
        abs=FLOAT_ERROR_NS / NS_PER_SECOND,
    )
    assert sink.waits[0] == pytest.approx(
        [
            (record["time_ns"] - packet["arrival_ns"]) / NS_PER_SECOND
            for record, packet in zip(deliveries, inputs["packets"], strict=True)
        ],
        rel=0,
        abs=FLOAT_ERROR_NS / NS_PER_SECOND,
    )
