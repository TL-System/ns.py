"""A recurring monitor must advance simulated time between observations."""

import pytest
import simpy

from ns.port.monitor import PortMonitor
from ns.port.port import Port


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_sampling_interval_fails_without_livelock(interval):
    env = simpy.Environment()
    PortMonitor(env, Port(env, 800), lambda: interval)
    # Bounded stepping proves rejection without hanging the baseline on t=0.
    with pytest.raises(ValueError, match="positive and finite"):
        for _ in range(5):
            env.step()
