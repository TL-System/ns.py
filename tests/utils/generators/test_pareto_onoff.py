import pytest

from ns.utils.generators import pareto_onoff_generator as pareto


def test_pareto_inverse_cdf_and_scale(monkeypatch):
    monkeypatch.setattr(pareto, "random", lambda: 0.75)
    assert pareto.paretovariate_generator(xmin=3, alpha=2) == 6


def test_on_duration_is_seconds_and_off_wait_includes_unsent_tail(monkeypatch):
    durations = iter([2.5, 4, 0.25, 3])
    monkeypatch.setattr(
        pareto, "paretovariate_generator", lambda *args: next(durations)
    )
    process = pareto.pareto_onoff_generator(on_rate=8000, pktsize=1000)
    # On [4, 6.5): emit at 4, 5, 6. Next on starts at 9.5.
    assert [next(process) for _ in range(4)] == [4, 1, 1, 3.5]


def test_packet_spacing_converts_bytes_to_bits(monkeypatch):
    monkeypatch.setattr(pareto, "paretovariate_generator", lambda *args: 1)
    process = pareto.pareto_onoff_generator(on_rate=16000, pktsize=1000)
    # Exactly two packets fit in the half-open one-second on period.
    assert [next(process) for _ in range(3)] == [1, 0.5, 1.5]


@pytest.mark.parametrize("parameters", [
    {"on_min": 0}, {"off_alpha": -1}, {"on_rate": 0},
    {"pktsize": -1}, {"on_alpha": float("nan")}, {"off_min": float("inf")},
])
def test_invalid_onoff_parameters_fail_without_yielding(parameters):
    with pytest.raises(ValueError):
        next(pareto.pareto_onoff_generator(**parameters))


@pytest.mark.parametrize("xmin,alpha", [(0, 2), (1, 0), (1, float("inf"))])
def test_invalid_pareto_parameters_raise(xmin, alpha):
    with pytest.raises(ValueError):
        pareto.paretovariate_generator(xmin, alpha)
