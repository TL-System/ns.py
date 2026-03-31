import pytest

from ns.packet.packet import Packet
from ns.packet.tcp_sink import TCPSink

simpy = pytest.importorskip("simpy")


class CaptureSink:
    def __init__(self):
        self.packets = []

    def put(self, packet):
        self.packets.append(packet)


def make_data_packet(seq, size=512, time=0.0, flow_id=1):
    return Packet(
        time=time,
        size=size,
        packet_id=seq,
        flow_id=flow_id,
        src="src",
        dst="dst",
    )


def make_sink():
    env = simpy.Environment()
    sink = TCPSink(env, rec_waits=False, rec_arrivals=False, rec_flow_ids=False)
    sink.out = CaptureSink()
    return env, sink


def ack_history(sink):
    return [packet.ack for packet in sink.out.packets]


def test_tcp_sink_pins_ack_for_out_of_order_and_duplicate_data():
    _, sink = make_sink()

    sink.put(make_data_packet(512))
    sink.put(make_data_packet(512))

    assert ack_history(sink) == [0, 0]
    assert sink.recv_buffer == [[512, 1024]]
    assert sink.next_seq_expected == 0


def test_tcp_sink_advances_ack_only_when_hole_is_filled():
    _, sink = make_sink()

    sink.put(make_data_packet(512))
    sink.put(make_data_packet(512))
    sink.put(make_data_packet(0))

    assert ack_history(sink) == [0, 0, 1024]
    assert sink.recv_buffer == [[0, 1024]]
    assert sink.next_seq_expected == 1024


def test_tcp_sink_merges_intervals_across_reorder_duplicate_and_fill():
    _, sink = make_sink()

    sink.put(make_data_packet(512))
    sink.put(make_data_packet(1536))
    sink.put(make_data_packet(0))
    sink.put(make_data_packet(512))
    sink.put(make_data_packet(1024))

    assert ack_history(sink) == [0, 0, 1024, 1024, 2048]
    assert sink.recv_buffer == [[0, 2048]]
    assert sink.next_seq_expected == 2048
