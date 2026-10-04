import pytest

from ns.flow.flow import AppType, Flow


def test_bulk_default_and_finite_volume_keep_existing_buffer_convention():
    assert Flow(0, "a", "b").init_send_buffer() is None
    flow = Flow(0, "a", "b", size=150)
    assert flow.init_send_buffer() == 150
    assert flow.next_send_buffer(100) == 0


def test_polling_retains_pending_arrival_and_includes_exact_boundary():
    intervals = iter([2, 3, 4])
    flow = Flow(
        0, "a", "b", typ=AppType.VIDEO,
        arrival_dist=lambda: next(intervals), size_dist=lambda: 100,
    )
    assert flow.init_send_buffer() == 0
    assert [flow.next_send_buffer(t) for t in [0, 1, 2, 4, 5, 5]] == [
        0, 0, 100, 0, 100, 0
    ]


def test_flow_start_finish_and_byte_cap_apply_to_arrivals():
    flow = Flow(
        0, "a", "b", size=150, start_time=3, finish_time=7,
        typ=AppType.GAME, arrival_dist=lambda: 1, size_dist=lambda: 100,
    )
    assert flow.next_send_buffer(3) == 0
    assert flow.next_send_buffer(6) == 150
    assert flow.next_send_buffer(100) == 0
    flow = Flow(
        1, "a", "b", finish_time=2, typ=AppType.VIDEO,
        arrival_dist=lambda: 1, size_dist=lambda: 100,
    )
    assert flow.next_send_buffer(100) == 100


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_flow_invalid_intervals_cannot_spin_in_poll(interval):
    intervals = iter([interval, 2])
    flow = Flow(
        0, "a", "b", typ=AppType.VIDEO,
        arrival_dist=lambda: next(intervals), size_dist=lambda: 100,
    )
    with pytest.raises(ValueError, match="interval"):
        flow.next_send_buffer(1)


def test_zero_byte_arrival_advances_stream_clock_before_next_data():
    sizes = iter([0, 100])
    flow = Flow(
        0, "a", "b", size=100, typ=AppType.VIDEO,
        arrival_dist=lambda: 1, size_dist=lambda: next(sizes),
    )
    assert flow.next_send_buffer(1) == 0
    assert flow.last_arrival == 1
    assert flow.next_send_buffer(2) == 100
    assert flow.next_send_buffer(3) == 0


def test_interval_smaller_than_clock_precision_cannot_spin_in_poll():
    intervals = iter([1, 1e21])
    flow = Flow(
        0, "a", "b", typ=AppType.VIDEO, last_arrival=1e20,
        arrival_dist=lambda: next(intervals), size_dist=lambda: 100,
    )
    with pytest.raises(ValueError, match="advance time"):
        flow.next_send_buffer(1e20)
