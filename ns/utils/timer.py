"""
Implements a simple timer that expires after a timeout value. When it expires, it runs
a provided callback function.
"""


class Timer:
    """ A simple timer that expires after a timeout value. When it expires, it runs a
        provided callback function.

        Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        timer_expired:
            The callback function that runs when the timer expires.
        timeout: float
            The timeout value.
    """
    def __init__(self, env, timer_id, timer_expired, timeout):
        self.env = env
        self.timer_id = timer_id,
        self.timer_expired = timer_expired
        self.timeout = timeout
        self.action = env.process(self.run())

    def run(self):
        """The generator function used in simulations."""
        yield self.env.timeout(self.timeout)
        self.timer_expired(self.timer_id)
