"""
Implements a simple timer that expires after a timeout value. When it expires, it runs
a provided callback function.
"""


class Timer:
    """A simple timer that expires after a timeout value. When it expires, it runs a
    provided callback function.

    Parameters
    ----------
    env: simpy.Environment
        The simulation environment.
    timer_id: int
        The id of this timer, used as a parameter when the timeout
        callback function is called.
    timeout_callback:
        The callback function that runs when the timer expires.
    timeout: float
        The timeout value.
    """

    def __init__(self, env, timer_id, timeout_callback, timeout):
        self.env = env
        self.timer_id = timer_id
        self.timeout_callback = timeout_callback
        self.timer_started = self.env.now
        self.timer_expiry = self.timer_started + timeout
        self.stopped = False
        self.action = env.process(self.run())

    def run(self):
        """The generator function used in simulations."""
        while True:
            if self.env.now < self.timer_expiry:
                yield self.env.timeout(self.timer_expiry - self.env.now)

            if not self.stopped:
                self.timeout_callback(self.timer_id)
            else:
                return

    def stop(self):
        """Stopping the timer."""
        self.stopped = True
        self.timer_expiry = self.env.now

    def restart(self, timeout, start_time=0):
        """Restarting the timer with a new timeout value."""
        if start_time == 0:
            self.timer_started = self.env.now
        else:
            self.timer_started = start_time

        self.timer_expiry = self.timer_started + timeout
