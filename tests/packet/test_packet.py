from ns.packet.packet import Packet


def test_packet_identity_units_and_mutable_metadata_are_per_packet():
    first = Packet(0.25, 12.5, 7, src="a", dst="b", flow_id="flow")
    second = Packet(0.5, 40, 8)
    first.prio["scheduler"] = 3
    first.perhop_time["port"] = 1.25

    assert (first.time, first.size, first.packet_id) == (0.25, 12.5, 7)
    assert (first.src, first.dst, first.flow_id) == ("a", "b", "flow")
    assert second.prio == {}
    assert second.perhop_time == {}
    assert first.delivered == 7
    assert Packet(0, 40, 9, delivered=100).delivered == 100
