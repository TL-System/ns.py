import pytest
import simpy

from ns.utils.timer import Timer


def test_timer_calls_a_one_shot_callback_once_and_finishes():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        # The old timer loops without yielding. Fail immediately on repetition
        # so this regression test cannot hang the entire test runner.
        assert len(calls) == 1

    timer = Timer(env, 7, callback, 2)
    env.run(until=5)

    assert calls == [(7, 2)]
    assert not timer.action.is_alive


def test_callback_can_restart_timer_for_a_later_expiry():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        if len(calls) == 1:
            timer.restart(3)
        else:
            timer.stop()

    timer = Timer(env, 7, callback, 2)
    env.run(until=6)

    assert calls == [(7, 2), (7, 5)]
    assert not timer.action.is_alive


@pytest.mark.parametrize("new_rto, expected_time", [(1, 3), (12, 14)])
def test_external_restart_moves_the_expiry_earlier_or_later(new_rto, expected_time):
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 10)
    env.run(until=2)
    timer.restart(new_rto)
    env.run(until=expected_time + 1)

    assert calls == [(7, expected_time)]


def test_stop_cancels_waiting_timer_without_a_callback():
    env = simpy.Environment()
    calls = []
    timer = Timer(env, 7, calls.append, 10)
    env.run(until=2)

    timer.stop()
    env.run(until=3)

    assert calls == []
    assert not timer.action.is_alive


@pytest.mark.parametrize("finish_process", [False, True])
def test_restart_rearms_a_stopped_timer(finish_process):
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 10)
    env.run(until=2)
    timer.stop()
    if finish_process:
        env.run(until=12)
    restart_time = env.now
    timer.restart(1)
    env.run(until=restart_time + 2)

    assert calls == [(7, restart_time + 1)]


def test_expired_timer_can_be_rearmed_externally():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        # Also makes the original timer terminate instead of spinning forever.
        timer.stop()

    timer = Timer(env, 7, callback, 1)
    env.run(until=2)
    timer.restart(1)
    env.run(until=4)

    assert calls == [(7, 1), (7, 3)]


def test_restart_accepts_an_explicit_zero_start_time():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 10)
    env.run(until=2)
    timer.restart(4, start_time=0)
    env.run(until=5)

    assert calls == [(7, 4)]


def test_restart_with_an_elapsed_deadline_expires_at_the_current_time():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 10)
    env.run(until=5)
    timer.restart(1, start_time=2)
    env.run(until=6)

    assert calls == [(7, 5)]


def test_zero_timeout_expires_on_a_simpy_turn():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 0)
    assert calls == []
    env.run()

    assert calls == [(7, 0)]


@pytest.mark.parametrize("rto", [-1, float("nan"), float("inf")])
def test_timer_rejects_invalid_timeout(rto):
    env = simpy.Environment()
    with pytest.raises(ValueError):
        Timer(env, 7, lambda timer_id: None, rto)


def test_rejected_restart_does_not_cancel_existing_timer():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 2)
    with pytest.raises(ValueError):
        timer.restart(-1)
    env.run(until=3)

    assert calls == [(7, 2)]


@pytest.mark.parametrize("start_time", [float("nan"), float("inf")])
def test_restart_rejects_invalid_start_time(start_time):
    timer = Timer(simpy.Environment(), 7, lambda timer_id: None, 2)

    with pytest.raises(ValueError):
        timer.restart(2, start_time=start_time)


def test_stop_before_initial_process_turn_does_not_invoke_callback():
    env = simpy.Environment()
    calls = []
    timer = Timer(env, 7, calls.append, 2)
    timer.stop()

    env.run()

    assert calls == []
    assert not timer.action.is_alive


def test_multiple_restarts_before_a_process_turn_use_the_latest_deadline():
    env = simpy.Environment()
    calls = []

    def callback(timer_id):
        calls.append((timer_id, env.now))
        timer.stop()

    timer = Timer(env, 7, callback, 10)
    timer.restart(1)
    timer.restart(3)
    env.run(until=4)

    assert calls == [(7, 3)]
