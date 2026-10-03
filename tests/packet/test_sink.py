import pytest
import simpy

from ns.packet.packet import Packet
from ns.packet.sink import PacketSink


def deliver(env, sink, at, packet):
    def receive():
        yield env.timeout(at - env.now)
        sink.put(packet)

    env.process(receive())


@pytest.mark.parametrize("rec_arrivals", [False, True])
def test_counters_and_first_last_arrivals_independent_of_recording(rec_arrivals):
    env = simpy.Environment()
    sink = PacketSink(env, rec_arrivals=rec_arrivals, rec_waits=False)
    deliver(env, sink, 0, Packet(0, 100, 1, flow_id="a"))
    deliver(env, sink, 2, Packet(1, 40, 2, flow_id="a"))
    deliver(env, sink, 3, Packet(2, 50, 3, flow_id="b"))
    env.run()

    assert dict(sink.packets_received) == {"a": 2, "b": 1}
    assert dict(sink.bytes_received) == {"a": 140, "b": 50}
    assert dict(sink.first_arrival) == {"a": 0, "b": 3}
    assert dict(sink.last_arrival) == {"a": 2, "b": 3}
    assert not sink.waits
    assert dict(sink.arrivals) == ({"a": [0, 2], "b": [3]} if rec_arrivals else {})


def test_interarrival_and_waits_are_per_source_with_snapshot_metadata():
    env = simpy.Environment()
    sink = PacketSink(env, absolute_arrivals=False, rec_flow_ids=False)
    packet = Packet(0.25, 100, 1, src="a", flow_id=1)
    packet.perhop_time["port"] = 0.5
    deliver(env, sink, 1, packet)
    deliver(env, sink, 2, Packet(1.5, 40, 2, src="b", flow_id=1))
    deliver(env, sink, 4, Packet(3, 50, 3, src="a", flow_id=2))
    env.run()
    packet.perhop_time["port"] = 99

    assert dict(sink.arrivals) == {"a": [1, 3], "b": [2]}
    assert dict(sink.waits) == {"a": [0.75, 1], "b": [0.5]}
    assert sink.perhop_times["a"] == [{"port": 0.5}, {}]
    assert dict(sink.packet_sizes) == {"a": [100, 50], "b": [40]}
    assert dict(sink.packet_times) == {"a": [0.25, 3], "b": [1.5]}


def test_debug_telemetry_handles_ten_simultaneous_arrivals(capsys):
    env = simpy.Environment()
    sink = PacketSink(env, debug=True)
    for i in range(10):
        sink.put(Packet(0, 100, i))

    assert sink.packets_received[0] == 10
    assert sink.bytes_received[0] == 1000
    assert sink.waits[0] == [0] * 10
    assert capsys.readouterr().out.count("arrived.") == 10
