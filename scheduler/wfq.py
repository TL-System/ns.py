"""
Models a WFQ/PGPS server.
"""
from utils import stampedstore

class WFQServer:
    """
    Parameters
    ----------
    env: simpy.Environment
        the simulation environment
    rate: float
        the bit rate of the port
    weights: A list of weights for each possible packet flow_id. We assume a simple assignment
        of flow ids to weights, i.e., flow_id = 0 corresponds to weights[0], etc.
    """
    def __init__(self, env, rate, weights, debug=False):
        self.env = env
        self.rate = rate
        self.weights = weights
        self.F_times = [0.0 for i in range(len(weights))]  # Initialize all the finish time variables

        # We keep track of the number of packets from each flow in the queue
        self.flow_queue_count = [0 for i in range(len(weights))]
        self.active_set = set()
        self.vtime = 0.0
        self.out = None
        self.packets_rec = 0
        self.packets_drop = 0
        self.debug = debug
        self.store = stampedstore.StampedStore(env)
        self.action = env.process(self.run())  # starts the run() method as a SimPy process
        self.last_update = 0.0


    def run(self):
        while True:
            msg = (yield self.store.get())
            self.last_update = self.env.now
            flow_id = msg.flow_id

            # update information about flow items in queue
            self.flow_queue_count[flow_id] -= 1
            if self.flow_queue_count[flow_id] == 0:
                self.active_set.remove(flow_id)

            # If end of busy period, reset virtual time and reinitialize finish times.
            if len(self.active_set) == 0:
                self.vtime = 0.0
                for i in range(len(self.F_times)):
                    self.F_times[i] = 0.0

            # Send message
            yield self.env.timeout(msg.size * 8.0 / self.rate)
            self.out.put(msg)


    def put(self, pkt):
        self.packets_rec += 1
        now = self.env.now
        flow_id = pkt.flow_id
        self.flow_queue_count[flow_id] += 1
        self.active_set.add(flow_id)

        weight_sum = 0.0
        for i in self.active_set:
            weight_sum += self.weights[i]

        self.vtime += (now - self.last_update) / weight_sum
        self.F_times[flow_id] = max(self.F_times[flow_id], self.vtime) + pkt.size * 8.0 / self.weights[flow_id]

        if self.debug:
            print("Flow id = {}, packet_id = {}, F_time = {}".format(flow_id, pkt.id, self.F_times[flow_id]))

        self.last_update = now

        return self.store.put((self.F_times[flow_id], pkt))
