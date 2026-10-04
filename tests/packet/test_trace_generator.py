import json
from pathlib import Path

import pytest
import simpy

from ns.packet.dist_generator import DistPacketGenerator
from ns.packet.trace_generator import TracePacketGenerator
from ns.port.port import Port
from tests.packet.test_dist_generator import Collector


def replay(tmp_path, text, **options):
    trace = tmp_path / "trace.txt"
    trace.write_text(text)
    env = simpy.Environment()
    source = TracePacketGenerator(env, "source", trace, **options)
    source.out = sink = Collector()
    return env, source, sink


def test_trace_offsets_times_preserves_ids_and_equal_timestamp_order(tmp_path):
    env, source, sink = replay(
        tmp_path, "  7 12 1 100\n7\t13\t1\t50\n9 2 3 25\n",
        initial_delay=2, rec_flow=True,
    )
    env.run()
    assert [(p.time, p.flow_id, p.packet_id, p.size) for p in sink.packets] == [
        (3, 7, 12, 100), (3, 7, 13, 50), (5, 9, 2, 25)
    ]
    assert source.packets_sent == 3
    assert source.time_rec == [3, 3, 5]
    assert source.size_rec == [100, 50, 25]


@pytest.mark.parametrize("arrival", [2, 3])
def test_trace_does_not_send_at_or_after_exclusive_finish(tmp_path, arrival):
    env, source, sink = replay(
        tmp_path, f"0 0 0 100\n0 1 {arrival} 100\n", finish=2,
    )
    env.run()
    assert [p.packet_id for p in sink.packets] == [0]
    assert (source.packets_sent, env.now) == (1, 2)


def test_fixed_flow_format_and_empty_trace(tmp_path):
    env, source, sink = replay(tmp_path, "12 0.5 100\n", flow_id="video")
    env.run()
    assert [(p.time, p.flow_id, p.packet_id) for p in sink.packets] == [
        (0.5, "video", 12)
    ]
    env, source, sink = replay(tmp_path, "")
    env.run()
    assert source.packets_sent == 0


@pytest.mark.parametrize("rows", [
    "0 0 2 100\n0 1 1 100\n", "0 0 -1 100\n",
    "0 0 nan 100\n", "0 0 inf 100\n", "0 0 1 -1\n",
])
def test_invalid_trace_timing_and_size_raise_value_error(tmp_path, rows):
    env, source, sink = replay(tmp_path, rows)
    with pytest.raises(ValueError):
        env.run()


def test_zero_byte_trace_packet_preserves_identity(tmp_path):
    env, source, sink = replay(tmp_path, "0 4 0 0\n0 5 0 10\n")
    env.run()
    assert [(p.packet_id, p.size) for p in sink.packets] == [(4, 0), (5, 10)]
    assert source.packets_sent == 2


@pytest.mark.parametrize("source_kind", ["trace", "distribution"])
def test_sources_replay_actual_days_cpu_fifo_input(tmp_path, source_kind):
    fixture_path = Path(__file__).resolve().parents[1] / "reference" / "days_fifo.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["reference"]["backend"] == "cpu"
    inputs = fixture["input"]
    rows = inputs["packets"]
    env = simpy.Environment()
    port = Port(env, rate=inputs["rate_bps"])
    port.out = sink = Collector()
    if source_kind == "trace":
        trace = tmp_path / "days.txt"
        trace.write_text("".join(
            f'{row["packet_id"]} {row["arrival_ns"] / 1e9} {row["size_bytes"]}\n'
            for row in rows
        ))
        source = TracePacketGenerator(env, "source", trace, flow_id=inputs["flow_id"])
    else:
        intervals = iter(
            (later["arrival_ns"] - earlier["arrival_ns"]) / 1e9
            for earlier, later in zip(rows, rows[1:])
        )
        sizes = iter(row["size_bytes"] for row in rows)
        source = DistPacketGenerator(
            env, "source", lambda: next(intervals), lambda: next(sizes),
            initial_delay=rows[0]["arrival_ns"] / 1e9,
            size=sum(row["size_bytes"] for row in rows), flow_id=inputs["flow_id"],
        )

    departures = []

    class Recorder:
        def put(self, packet):
            # Dist assigns consecutive local IDs; translate them to tape identities.
            identity = (rows[packet.packet_id]["packet_id"]
                        if source_kind == "distribution" else packet.packet_id)
            departures.append((identity, env.now * 1e9))
            sink.put(packet)

    source.out = port
    port.out = Recorder()
    # Drain the finite tape; numeric run(until=t) excludes ordinary events at t.
    env.run()
    expected = fixture["output"]["departures"]
    assert [identity for identity, _ in departures] == [
        row["packet_id"] for row in expected
    ]
    assert [time for _, time in departures] == pytest.approx(
        [r["time_ns"] for r in expected], rel=0, abs=1e-6,
    )
    assert source.packets_sent == len(rows)
    assert sum(p.size for p in sink.packets) == (
        fixture["output"]["summary"]["departed_bytes"]
    )
