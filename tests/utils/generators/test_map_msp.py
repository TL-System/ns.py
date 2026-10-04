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
    assert math.isfinite(next(process))
