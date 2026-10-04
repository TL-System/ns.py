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


def test_overlap_and_nested_duplicates_cannot_ack_across_a_gap():
    _, sink = make_sink()

    # These intervals bridge each other but leave the first 100 bytes missing.
    for seq, size in [(200, 100), (150, 100), (175, 10), (100, 50)]:
        sink.put(make_data_packet(seq, size))
    assert ack_history(sink) == [0, 0, 0, 0]
    assert sink.recv_buffer == [[100, 300]]

    sink.put(make_data_packet(0, 125))
    sink.put(make_data_packet(50, 200))
    sink.put(make_data_packet(275, 50))
    assert ack_history(sink) == [0, 0, 0, 0, 300, 300, 325]
    assert sink.recv_buffer == [[0, 325]]


def test_unique_application_delivery_is_distinct_from_physical_arrivals():
    env = simpy.Environment()
    sink = TCPSink(env)
    sink.out = CaptureSink()
    delivered = []

    def receive():
        for seq, size in [(100, 100), (100, 100), (0, 150), (50, 100)]:
            yield env.timeout(0.1)
            sink.put(make_data_packet(seq, size, time=0.0))
            delivered.append(sink.bytes_delivered)

    env.process(receive())
    env.run()
    # Out-of-order data is buffered, then delivered once when its gap closes.
    assert delivered == [0, 0, 200, 200]
    assert sink.packets_received[1] == 4
    assert sink.bytes_received[1] == 450
    assert sink.waits[1] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert sink.arrivals[1] == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_ack_echoes_sampling_metadata_without_mutating_data():
    _, sink = make_sink()
    data = make_data_packet(0, 123, time=0.25, flow_id=9)
    data.delivered_time = 0.1
    data.first_sent_time = 0.2
    data.delivered = 50
    data.lost = 12
    data.is_app_limited = True
    before = vars(data).copy()

    sink.put(data)
    acknowledgment = sink.out.packets[0]
    assert (acknowledgment.ack, acknowledgment.size, acknowledgment.flow_id) == (
        123, 40, 10009
    )
    for field in ("time", "delivered_time", "first_sent_time", "delivered",
                  "lost", "is_app_limited"):
        assert getattr(acknowledgment, field) == getattr(data, field)
    assert vars(data) == before
