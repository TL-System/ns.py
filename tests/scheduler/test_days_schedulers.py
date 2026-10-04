"""Compare explicit schedules with recorded observations from actual Days CPU."""

import hashlib
import json
from pathlib import Path

import pytest
import simpy

from ns.packet.packet import Packet
from ns.packet.sink import PacketSink
from ns.port.wire import Wire
from ns.scheduler.drr import DRRServer
from ns.scheduler.sp import SPServer
from ns.scheduler.wfq import WFQServer


REFERENCE = Path(__file__).resolve().parents[1] / "reference"
FIXTURE = json.loads((REFERENCE / "days_schedulers.json").read_text(encoding="utf-8"))
CASES = {case["name"]: case for case in FIXTURE["cases"]}
NS_PER_SECOND = 1_000_000_000
# All serialization intervals are integral nanoseconds. One femtosecond covers
# only floating-point accumulation; even one Days nanosecond must fail.
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
    """Check decisions first, then times without unrelated global event order."""
    assert [packet_id for packet_id, _ in actual] == [
        record["packet_id"] for record in expected
    ]
    assert [time for _, time in actual] == pytest.approx(
        [record["time_ns"] for record in expected], rel=0, abs=FLOAT_ERROR_NS
    )


def run_python(case):
    inputs = case["input"]
    env = simpy.Environment()
    config = inputs["scheduler"]
    if config["kind"] == "sp":
        server = SPServer(env, inputs["rate_bps"], config["priorities"])
    elif config["kind"] == "drr":
        server = DRRServer(env, inputs["rate_bps"], config["weights"])
        assert list(server.quantum.values()) == config["quanta_bytes"]
    else:
        assert config["kind"] == "wfq"
        server = WFQServer(env, inputs["rate_bps"], config["weights"])
    wire = Wire(env, delay_dist=lambda: inputs["propagation_ns"] / NS_PER_SECOND)
    sink = IdentitySink(env)
    departures = DepartureRecorder(env, wire)
    server.out = departures
    wire.out = sink
    packets = [
        Packet(
            time=record["arrival_ns"] / NS_PER_SECOND,
            size=record["size_bytes"],
            packet_id=record["packet_id"],
            flow_id=record["flow_id"],
        )
        for record in inputs["packets"]
    ]

    def arrivals():
        """Wait between timestamps and inject each equal-time batch in input order."""
        previous_ns = None
        for record, packet in zip(inputs["packets"], packets, strict=True):
            if record["arrival_ns"] != previous_ns:
                yield env.timeout(
                    (record["arrival_ns"] - (previous_ns or 0)) / NS_PER_SECOND
                )
                previous_ns = record["arrival_ns"]
            server.put(packet)

    env.process(arrivals())
    # Days includes its stop time. Drain this finite input, including the final
    # delivery at the cutoff; there are no emissions beyond the recorded stop.
    env.run()
    assert env.now * NS_PER_SECOND == pytest.approx(
        inputs["stop_time_ns"], rel=0, abs=FLOAT_ERROR_NS
    )
    assert server.packets_received == len(packets)
    assert server.total_packets() == 0
    assert server.packet_in_service() is None
    assert all(server.size(packet.flow_id) == 0 for packet in packets)
    assert all(server.byte_size(packet.flow_id) == 0 for packet in packets)
    assert sum(sink.packets_received.values()) == len(packets)
    assert sum(sink.bytes_received.values()) == sum(p.size for p in packets)
    assert len({id(packet) for packet in sink.packets}) == len(packets)
    assert {id(packet) for packet in sink.packets} == {id(p) for p in packets}
    return departures.records, sink.records


def test_scheduler_fixture_provenance_and_conservation():
    reference = FIXTURE["reference"]
    assert reference["revision"] == "9ff20eac16dcdf752510b05cbcf526684dc05146"
    assert reference["backend"] == "cpu"
    assert reference["workers"] == 2
    assert reference["observation_mode"] == "full"
    assert reference["scalar_equal"] is True
    for filename, key in (
        ("days_schedulers.rs", "helper_source_sha256"),
        ("days_schedulers.Cargo.lock", "helper_lock_sha256"),
    ):
        assert hashlib.sha256((REFERENCE / filename).read_bytes()).hexdigest() == (
            reference[key]
        )
    for case in CASES.values():
        inputs, output = case["input"], case["output"]
        assert inputs["route"] == [0, 1]
        assert inputs["arrival_node"] == 1
        assert inputs["queue_capacity_packets"] == 0
        assert inputs["class_mapping"] == "flow_id"
        assert all(p["class_id"] == p["flow_id"] for p in inputs["packets"])
        assert output["pending_events"] == output["resident_packets"] == 0
        packet_count = len(inputs["packets"])
        byte_count = sum(p["size_bytes"] for p in inputs["packets"])
        summary = output["summary"]
        for prefix in ("admitted", "departed", "received"):
            assert summary[f"{prefix}_packets"] == packet_count
            assert summary[f"{prefix}_bytes"] == byte_count
        assert summary["dropped_packets"] == summary["dropped_bytes"] == 0
        assert sorted(p["packet_id"] for p in output["departures"]) == sorted(
            p["packet_id"] for p in inputs["packets"]
        )
        admitted = [
            record for record in output["arrivals"]
            if record["disposition"] == "admitted"
        ]
        assert [(r["packet_id"], r["time_ns"]) for r in admitted] == [
            (p["packet_id"], p["arrival_ns"]) for p in inputs["packets"]
        ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "sp_boundaries_ties_idle",
            [
                (3, 250), (9, 375), (12, 500), (0, 1500), (15, 1625),
                (6, 2125), (18, 5125),
            ],
        ),
        (
            "drr_credit_carry_idle",
            [
                (3, 1000), (6, 3500), (12, 4000), (0, 8000), (9, 9000),
                (15, 17000),
            ],
        ),
        ("drr_activation_order_difference", [(3, 1000), (0, 2000)]),
        ("wfq_tags_ties_idle", [(3, 500), (0, 1500), (6, 3000), (9, 6000)]),
        (
            "wfq_active_clock_difference",
            [(0, 10), (6, 23), (9, 37), (12, 47), (3, 147)],
        ),
    ],
)
def test_days_cpu_observations_have_independent_expected_departures(name, expected):
    # These constants describe decisions and serialization, independently of
    # Python's state. Known differences are preserved instead of hidden by tolerance.
    case = CASES[name]
    assert case["output"]["departures"] == [
        {"packet_id": packet_id, "time_ns": time} for packet_id, time in expected
    ]
    delivered = [
        record for record in case["output"]["arrivals"]
        if record["disposition"] == "delivered"
    ]
    assert [(record["packet_id"], record["time_ns"]) for record in delivered] == [
        (packet_id, time + case["input"]["propagation_ns"])
        for packet_id, time in expected
    ]
    assert delivered[-1]["time_ns"] == case["input"]["stop_time_ns"]


@pytest.mark.parametrize(
    "name",
    [
        "sp_boundaries_ties_idle",
        "drr_credit_carry_idle",
        "wfq_tags_ties_idle",
        # Days selects packet 9 after packet 6 departs at 23 ns; ideal GPS
        # would select packet 12 then, changing the departure identity order.
        "wfq_active_clock_difference",
    ],
)
def test_shared_scheduler_decisions_and_times_match_days_cpu(name):
    case = CASES[name]
    departures, deliveries = run_python(case)
    assert_observations(departures, case["output"]["departures"])
    assert_observations(
        deliveries,
        [r for r in case["output"]["arrivals"] if r["disposition"] == "delivered"],
    )


def test_drr_active_fifo_order_differs_from_days_numeric_class_rotation():
    case = CASES["drr_activation_order_difference"]
    departures, deliveries = run_python(case)
    # Class 1 activates first, then class 0. Textbook DRR's active FIFO serves
    # that order. Days starts its numeric class rotation at 0 and serves 0 first.
    expected = [
        {"packet_id": 0, "time_ns": 1000},
        {"packet_id": 3, "time_ns": 2000},
    ]
    assert_observations(departures, expected)
    assert_observations(
        deliveries,
        [
            {"packet_id": r["packet_id"], "time_ns": r["time_ns"] + 100}
            for r in expected
        ],
    )
    assert [packet_id for packet_id, _ in departures] != [
        r["packet_id"] for r in case["output"]["departures"]
    ]
