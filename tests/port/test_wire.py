import pytest
import simpy

from ns.packet.packet import Packet
from ns.port.port import Port
from ns.port.wire import Wire


class CaptureSink:
    def __init__(self, env):
        self.env = env
        self.received = []

    def put(self, packet):
        self.received.append((self.env.now, packet))


def test_fixed_propagation_overlaps_and_adds_to_serialization():
    env = simpy.Environment()
    port = Port(env, rate=800)
    wire = Wire(env, lambda: 2)
    sink = CaptureSink(env)
    port.out = wire
    wire.out = sink
    packets = [Packet(0, 100, i) for i in range(3)]
    for packet in packets:
        port.put(packet)
    env.run()

    assert sink.received == [(3, packets[0]), (4, packets[1]), (5, packets[2])]
    assert wire.packets_rec == 3
    assert all(packet.time == 0 for packet in packets)


def test_variable_delay_preserves_wire_fifo_without_extra_serialization():
    env = simpy.Environment()
    delays = iter([5, 1, 0])
    wire = Wire(env, lambda: next(delays))
    sink = CaptureSink(env)
    wire.out = sink
    packets = [Packet(0, 100, i) for i in range(3)]
    for packet in packets:
        wire.put(packet)
    env.run()

    assert sink.received == [(5, packet) for packet in packets]


def test_entry_time_belongs_to_wire_when_packet_is_shared():
    env = simpy.Environment()
    delays = iter([10, 12])
    first_wire = Wire(env, lambda: next(delays))
    second_wire = Wire(env, lambda: 0)
    first_wire.out = CaptureSink(env)
    second_wire.out = CaptureSink(env)
    head = Packet(0, 100, 1)
    shared = Packet(0, 100, 2)
    first_wire.put(head)
    first_wire.put(shared)

    def second_path():
        yield env.timeout(3)
        second_wire.put(shared)

    env.process(second_path())
    env.run()

    assert first_wire.out.received == [(10, head), (12, shared)]
    assert second_wire.out.received == [(3, shared)]


def test_loss_schedule_drops_identity_and_does_not_block_following_packet(monkeypatch):
    env = simpy.Environment()
    observed_ids = []

    def loss(packet_id):
        observed_ids.append(packet_id)
        return 1 if packet_id == 2 else 0

    monkeypatch.setattr("ns.port.wire.random.uniform", lambda _a, _b: 0.5)
    wire = Wire(env, lambda: 1, loss_dist=loss)
    wire.out = CaptureSink(env)
    packets = [Packet(0, 100, i) for i in range(3)]
    for packet in packets:
        wire.put(packet)
    env.run()

    assert observed_ids == [0, 1, 2]
    assert wire.out.received == [(1, packets[0]), (1, packets[1])]
    assert wire.packets_rec == 3


def test_numeric_stop_excludes_delivery_at_boundary():
    env = simpy.Environment()
    wire = Wire(env, lambda: 1)
    wire.out = CaptureSink(env)
    packet = Packet(0, 100, 1)
    wire.put(packet)
    env.run(until=1)

    assert wire.out.received == []
    env.run()
    assert wire.out.received == [(1, packet)]
