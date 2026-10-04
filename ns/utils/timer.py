"""A restartable, one-shot callback timer using simulation seconds."""

import math

import simpy


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
    rto: float
        A finite, nonnegative timeout in seconds. A callback may call ``restart()``
        to rearm this timer; otherwise expiration ends the process.
    """

    def __init__(self, env, timer_id, timeout_callback, rto):
        if not math.isfinite(rto) or rto < 0:
            raise ValueError("rto must be finite and nonnegative.")
        self.env = env
        self.timer_id = timer_id
        self.timeout_callback = timeout_callback
        self.rto = rto
        self.timer_started = self.env.now
        self.timer_expiry = self.timer_started + rto
        self.stopped = False
        self.action = env.process(self.run())

    def run(self):
        """Wait for the deadline, or wake early on restart/cancellation."""
        while not self.stopped:
            try:
                # Past deadlines expire on a new SimPy turn at the current time;
                # even a zero timeout yields before invoking user code.
                yield self.env.timeout(max(0, self.timer_expiry - self.env.now))
            except simpy.Interrupt:
                # A restart may move the deadline in either direction. Re-read
                # it rather than allowing the previous wait to fire a callback.
                continue

            # Disarm before invoking the callback. Only an explicit restart
            # rearms it, so a one-shot callback cannot loop at the same time.
            self.stopped = True
            self.timeout_callback(self.timer_id)

    def stop(self):
        """Cancel the callback and wake a waiting process so it can finish."""
        self.stopped = True
        self.timer_expiry = self.env.now
        if self.action.is_alive and self.env.active_process is not self.action:
            self.action.interrupt()

    def restart(self, revised_rto, start_time=None):
        """Rearm relative to now, or to an explicit start time in seconds."""
        if not math.isfinite(revised_rto) or revised_rto < 0:
            raise ValueError("rto must be finite and nonnegative.")
        if start_time is not None and not math.isfinite(start_time):
            raise ValueError("start_time must be finite.")
        self.rto = revised_rto
        # None means omitted; zero is a valid original transmission timestamp.
        self.timer_started = self.env.now if start_time is None else start_time
        self.timer_expiry = self.timer_started + revised_rto
        self.stopped = False
        if self.action.is_alive:
            # TCP callbacks restart their own timer. A SimPy process cannot
            # interrupt itself; after the callback it will wait again normally.
            if self.env.active_process is not self.action:
                self.action.interrupt()
        else:
            self.action = self.env.process(self.run())
