import math

import numpy as np
import pytest

from ns.utils.generators import MAP_MSP_generator as map_generator


def test_stationary_solvers_satisfy_independent_balance_equations():
    q = np.array([[-2.0, 2.0], [3.0, -3.0]])
    pi = map_generator.solve_CTMC(q)
    np.testing.assert_allclose(pi, [[0.6, 0.4]])
    np.testing.assert_allclose(pi @ q, [[0, 0]], atol=1e-15)
    p = np.array([[0.8, 0.2], [0.3, 0.7]])
    np.testing.assert_allclose(map_generator.solve_DTMC(p), pi)


@pytest.mark.parametrize("q", [
    [[1, -1], [-1, 1]], [[-1, 1, 0]], [[float("nan")]],
])
def test_ctmc_rejects_invalid_rates_or_shapes(q):
    with pytest.raises(ValueError):
        map_generator.solve_CTMC(np.array(q))


@pytest.mark.parametrize("p", [[[0.4, 0.4], [0.2, 0.8]], [[-1, 2], [0, 1]]])
def test_dtmc_rejects_invalid_transition_probabilities(p):
    with pytest.raises(ValueError):
        map_generator.solve_DTMC(p)


def test_map_transition_accumulates_silent_sojourns(monkeypatch):
    # State 0 silently moves to state 1 at rate 2; state 1 emits at rate 4.
    draws = iter([math.exp(-1), 0.5, math.exp(-2), 0.5])
    monkeypatch.setattr(map_generator, "rand", lambda: next(draws))
    process = map_generator.BMAP_generator(
        [np.array([[-2, 2], [0, -4]]), np.array([[0, 0], [4, 0]])], initial=0,
    )
    assert next(process) == pytest.approx(1)


def test_bmap_batch_choice_and_stationary_initial_state(monkeypatch):
    # One state: total rate 4, rate-1 singleton arrivals, rate-3 batches of two.
    draws = iter([0.5, math.exp(-2), 0.25, math.exp(-4), 0.1])
    monkeypatch.setattr(map_generator, "rand", lambda: next(draws))
    process = map_generator.BMAP_generator([
        np.array([[-4.0]]), np.array([[1.0]]), np.array([[3.0]]),
    ])
    assert next(process) == pytest.approx([0.5, 2])
    assert next(process) == pytest.approx([1, 1])


@pytest.mark.parametrize("matrices", [
    [np.array([[-1, -1], [0, -1]]), np.array([[2, 0], [0, 1]])],
    [np.array([[1.0]]), np.array([[-1.0]])],
    [np.array([[0.0]]), np.array([[0.0]])],
    [np.array([[-1, 1], [1, -1]]), np.zeros((2, 2))],
    [np.array([[float("nan")]]), np.array([[1.0]])],
])
def test_invalid_or_nonabsorbing_map_fails_without_sampling(matrices):
    assert not map_generator.check_BMAP_representation(matrices)


@pytest.mark.parametrize("initial", [-1, 2, 0.5])
def test_initial_state_must_index_a_phase(initial):
    with pytest.raises(ValueError, match="initial"):
        next(map_generator.BMAP_generator([
            np.array([[-1.0]]), np.array([[1.0]])
        ], initial=initial))


def test_zero_uniform_endpoint_still_gives_finite_holding_time(monkeypatch):
    monkeypatch.setattr(map_generator, "rand", lambda: 0)
    process = map_generator.BMAP_generator([np.array([[-1]]), np.array([[1]])])
    interval = next(process)
    assert isinstance(interval, float) and math.isfinite(interval)


def test_ctmc_rounding_rebalances_diagonals_without_negative_stationarity():
    q = np.array([
        [-1e-4, 1e-4, 0], [0, -1e-4, 1e-4], [0, 1e-4, -0.95e-4],
    ])
    original = q.copy()
    pi = map_generator.solve_CTMC(q)
    # State 0 is transient; states 1 and 2 exchange at equal rate 1e-4.
    np.testing.assert_allclose(pi, [[0, 0.5, 0.5]], atol=1e-14)
    assert np.all(pi >= 0)
    np.testing.assert_array_equal(q, original)


def test_dtmc_rounding_normalizes_each_transition_row():
    p = np.array([[0.8, 0.200001], [0.3, 0.7]])
    original = p.copy()
    pi = map_generator.solve_DTMC(p)
    # Row 0 has mass 1.000001, so its move probability is 0.200001/1.000001.
    move = 0.200001 / 1.000001
    expected_first = 0.3 / (0.3 + move)
    np.testing.assert_allclose(pi, [[expected_first, 1 - expected_first]], atol=1e-14)
    np.testing.assert_allclose(pi @ (p / p.sum(axis=1)[:, None]), pi, atol=1e-14)
    np.testing.assert_array_equal(p, original)


def test_rounded_one_phase_map_initializes_and_keeps_its_holding_rate(monkeypatch):
    draws = iter([0.5, math.exp(-2), 0.5])
    monkeypatch.setattr(map_generator, "rand", lambda: next(draws))
    matrices = [np.array([[-1.0]]), np.array([[1.000001]])]
    assert map_generator.check_BMAP_representation(matrices)
    # All events return to the only phase; D0 still gives a one-second mean.
    assert next(map_generator.BMAP_generator(matrices)) == pytest.approx(2)


@pytest.mark.parametrize("initial_draw,phase", [(0.49, 1), (0.4999998, 2)])
def test_rounded_map_stationarity_matches_sampled_phase_rates(
    monkeypatch, initial_draw, phase,
):
    q = np.array([
        [-1e-4, 1e-4, 0], [0, -1e-4, 1e-4], [0, 1e-4, -0.95e-4],
    ])
    arrivals = np.diag([1, 2, 3])
    matrices = [q - arrivals, arrivals]
    assert map_generator.check_BMAP_representation(matrices)

    # State 2's event choices have mass 3.0001 and holding rate 3.000095.
    # Thus its actual 2->1 rate is 1e-4 * 3.000095/3.0001. State 1's
    # 1->2 rate stays 1e-4, so pi[1] is slightly below 0.5, not exactly 0.5.
    rate_back = 1e-4 * 3.000095 / 3.0001
    phase_one_probability = rate_back / (1e-4 + rate_back)
    solver = map_generator.solve_CTMC

    def check_stationarity(generator):
        pi = solver(generator)
        assert np.all(pi >= 0)
        np.testing.assert_allclose(
            pi, [[0, phase_one_probability, 1 - phase_one_probability]],
            atol=1e-14,
        )
        return pi

    monkeypatch.setattr(map_generator, "solve_CTMC", check_stationarity)
    draws = iter([initial_draw, math.exp(-1), 0.5])
    monkeypatch.setattr(map_generator, "rand", lambda: next(draws))
    interval = next(map_generator.BMAP_generator(matrices))
    # The first emitted packet is a self-arrival in the selected initial phase.
    holding_rate = [1.0001, 2.0001, 3.000095][phase]
    assert interval == pytest.approx(1 / holding_rate)
