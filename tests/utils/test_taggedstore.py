import pytest
import simpy

from ns.utils.taggedstore import TaggedStore


def test_lower_tags_depart_first_and_ties_preserve_put_order():
    env = simpy.Environment()
    store = TaggedStore(env)
    # Plain objects cannot be compared. Equal tags must never compare payloads.
    first, second, third, fourth = (object() for _ in range(4))
    for tag, item in [(2, fourth), (1, first), (1, second), (1, third)]:
        store.put((tag, item))

    assert [store.get().value for _ in range(4)] == [first, second, third, fourth]


def test_capacity_blocks_put_until_a_get_and_retains_equal_tag_order():
    env = simpy.Environment()
    store = TaggedStore(env, capacity=1)
    items = [object(), object(), object()]
    puts = [store.put((1, item)) for item in items]
    observed = []

    def consume():
        yield env.timeout(1)
        for _ in items:
            observed.append((env.now, (yield store.get())))
            yield env.timeout(1)

    env.process(consume())
    assert [event.triggered for event in puts] == [True, False, False]
    env.run()

    assert observed == list(zip([1, 2, 3], items))
    assert all(event.triggered for event in puts)


def test_cancelled_pending_put_is_never_delivered():
    env = simpy.Environment()
    store = TaggedStore(env, capacity=1)
    first, cancelled, last = object(), object(), object()
    store.put((1, first))
    blocked = store.put((0, cancelled))
    store.put((1, last))
    blocked.cancel()
    observed = []

    def consume():
        for _ in range(2):
            observed.append((yield store.get()))

    env.process(consume())
    env.run()

    assert observed == [first, last]
    assert not blocked.triggered
    assert store.items == []


def test_get_waits_for_a_later_put_and_preserves_identity():
    env = simpy.Environment()
    store = TaggedStore(env)
    item = object()
    get_event = store.get()

    def supply():
        yield env.timeout(2)
        yield store.put((4, item))

    env.process(supply())
    env.run(until=get_event)

    assert env.now == 2
    assert get_event.value is item


@pytest.mark.parametrize("capacity", [0, -1, float("nan")])
def test_invalid_capacity_is_rejected(capacity):
    with pytest.raises(ValueError):
        TaggedStore(simpy.Environment(), capacity=capacity)
