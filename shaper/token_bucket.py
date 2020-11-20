"""
Models an ideal token bucket shaper.
"""
import simpy

class ShaperTokenBucket:
    """ The token bucket size should be greater than the size of the largest packet that 
    can occur on input. If this is not the case we always accumulate enough tokens to let
    the current packet pass based on the average rate. This may not be the behavior you desire.

    Parameters
    ----------
    env : simpy.Environment
        the simulation environment
    rate : float
        the token arrival rate in bits
    b_size : Number
        a token bucket size in bytes
    peak : Number or None for infinite peak
        the peak sending rate of the buffer (quickest time two packets could be sent)
    """
    def __init__(self, env, rate, b_size, peak=None, debug=False):
        self.store = simpy.Store(env)
        self.rate = rate
        self.env = env
        self.out = None
        self.packets_rec = 0
        self.packets_sent = 0
        self.b_size = b_size
        self.peak = peak

        self.current_bucket = b_size  # Current size of the bucket in bytes
        self.update_time = 0.0  # Last time the bucket was updated
        self.debug = debug
        self.busy = 0  # Used to track if a packet is currently being sent ?
        self.action = env.process(self.run())  # starts the run() method as a SimPy process


    def run(self):
        while True:
            msg = (yield self.store.get())
            now = self.env.now

            #  Add tokens to bucket based on current time
            self.current_bucket = min(self.b_size, self.current_bucket + self.rate*(now-self.update_time)/8.0)
            self.update_time = now

            #  Check if there are enough tokens to allow packet to be sent
            #  If not we will wait to accumulate enough tokens to let this packet pass
            #  regardless of the bucket size.
            if msg.size > self.current_bucket:  # Need to wait for bucket to fill before sending
                yield self.env.timeout((msg.size - self.current_bucket)*8.0/self.rate)
                self.current_bucket = 0.0
                self.update_time = self.env.now
            else:
                self.current_bucket -= msg.size
                self.update_time = self.env.now

            # Send packet
            if not self.peak:  # Infinite peak rate
                self.out.put(msg)
            else:
                yield self.env.timeout(msg.size*8.0/self.peak)
                self.out.put(msg)

            self.packets_sent += 1
            if self.debug:
                print(msg)


    def put(self, pkt):
        self.packets_rec += 1
        return self.store.put(pkt)
