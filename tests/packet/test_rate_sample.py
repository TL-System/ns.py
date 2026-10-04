"""Independent byte/time observations for delivery-rate sampling."""

import pytest

from ns.packet.packet import Packet
from ns.packet.rate_sample import Connection, RateSample


def sent(sample, connection, now=0, size=100, flight=0):
    packet = Packet(now, size, 0)
    sample.send_packet(packet, connection, flight, now)
    return packet


def test_zero_time_send_and_duplicate_consumption():
    sample, connection = RateSample(), Connection()
    packet = sent(sample, connection)
    sample.updaterate_sample(packet, connection, 0.1)
    sample.updaterate_sample(packet, connection, 0.2)
    assert connection.delivered == 100
    assert sample.update_sample_group(connection, 0.1)
    assert sample.delivery_rate == pytest.approx(1000)


def test_zero_interval_is_invalid_without_division():
    sample, connection = RateSample(), Connection()
    sample.updaterate_sample(sent(sample, connection), connection, 0)
    assert not sample.update_sample_group(connection)
    assert sample.delivery_rate == 0


def test_ack_group_does_not_reuse_old_packet_snapshot():
    sample, connection = RateSample(), Connection()
    sample.updaterate_sample(sent(sample, connection), connection, 0.1)
    assert sample.update_sample_group(connection)
    sample.begin_ack()
    assert not sample.update_sample_group(connection)
    assert sample.delivery_rate == 0
    assert sample.delivered == 0


def test_short_interval_clears_previous_rate():
    sample, connection = RateSample(), Connection()
    sample.updaterate_sample(sent(sample, connection), connection, 0.1)
    sample.update_sample_group(connection)
    sample.begin_ack()
    sample.updaterate_sample(sent(sample, connection, 0.2), connection, 0.21)
    assert not sample.update_sample_group(connection, 0.05)
    assert sample.delivery_rate == 0


def test_send_spacing_bounds_ack_compression():
    sample, connection = RateSample(), Connection()
    first = sent(sample, connection, 0, flight=0)
    second = sent(sample, connection, 0.2, flight=100)
    sample.updaterate_sample(first, connection, 0.21)
    sample.updaterate_sample(second, connection, 0.21)
    assert sample.update_sample_group(connection)
    assert sample.delivered == 200
    assert sample.delivery_rate == pytest.approx(200 / 0.21)
    assert sample.send_elapsed == pytest.approx(0.2)


def test_attempt_clock_is_distinct_from_original_latency_clock():
    sample, connection = RateSample(), Connection()
    packet = sent(sample, connection, 1)
    packet.time = 0  # A retransmission preserves the original latency timestamp.
    sample.updaterate_sample(packet, connection, 1.1)
    assert sample.update_sample_group(connection)
    assert sample.send_elapsed == 0
    assert sample.delivery_rate == pytest.approx(1000)
    assert connection.first_sent_time == 1


def test_loss_delta_and_application_limited_boundary():
    sample, connection = RateSample(), Connection()
    connection.mark_connection_app_limited(100)
    packet = sent(sample, connection)
    connection.lost = 100
    sample.updaterate_sample(packet, connection, 0.1)
    sample.update_sample_group(connection)
    assert sample.newly_lost == 100
    assert connection.is_app_limited == 100  # Clear only after passing boundary.
    sample.begin_ack()
    sample.updaterate_sample(sent(sample, connection, 0.2), connection, 0.3)
    sample.update_sample_group(connection)
    assert sample.newly_lost == 0
    assert connection.is_app_limited == 0


def test_window_limited_sender_is_not_marked_application_limited():
    connection = Connection()
    connection.write_seq = 100
    connection.is_cwnd_limited = True
    connection.check_if_application_limited(100, 100, 100)
    assert connection.is_app_limited == 0


def test_send_elapsed_bounds_compressed_ack_group():
    sample, connection = RateSample(), Connection()
    sample.updaterate_sample(sent(sample, connection), connection, 0.1)
    sample.update_sample_group(connection)
    sample.begin_ack()
    second = sent(sample, connection, 0.2, flight=100)
    third = sent(sample, connection, 0.3, flight=200)
    sample.updaterate_sample(second, connection, 0.31)
    sample.updaterate_sample(third, connection, 0.31)
    assert sample.update_sample_group(connection)
    assert sample.send_elapsed == pytest.approx(0.3)
    assert sample.ack_elapsed == pytest.approx(0.21)
    assert sample.delivery_rate == pytest.approx(200 / 0.3)
