"""
Models a Deficit Round Robin (DRR) server.

Source: M. Shreedhar and G. Varghese, "Efficient Fair Queuing Using Deficit Round-Robin," IEEE/ACM
Tran. Networking, vol. 4, no. 3, June 1996.
"""

import simpy

class DRRServer:
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
    MIN_QUANTUM = 100

    def __init__(self, env, rate, weights, debug=False):
        self.env = env
        self.rate = rate
        self.weights = weights
        self.deficit = [0.0 for i in range(len(weights))]
        self.head_of_line = {}
        self.flow_queue_count = [0 for i in range(len(weights))]
        self.quantum = [self.MIN_QUANTUM * x / min(weights) for x in weights]
        self.active_set = set()

        # One FIFO queue for each flow_id
        self.stores = {}

        self.packets_rec = 0
        self.out = None

        # We keep track of the number of packets from each flow in the queue
        self.debug = debug
        self.action = env.process(self.run())  # starts the run() method as a SimPy process


    def run(self):
        while True:
            for flow_id, count in enumerate(self.flow_queue_count):
                if count > 0:
                    self.deficit[flow_id] += self.quantum[flow_id]

                    while self.deficit[flow_id] > 0 and self.flow_queue_count[flow_id] > 0:
                        if flow_id in self.head_of_line:
                            packet = self.head_of_line[flow_id]
                            del self.head_of_line[flow_id]
                        else:
                            store = self.stores[flow_id]
                            packet = yield store.get()

                        assert flow_id == packet.flow_id

                        if packet.size <= self.deficit[flow_id]:
                            # Send the packet
                            yield self.env.timeout(packet.size * 8.0 / self.rate)
                            self.out.put(packet)
                            print(f"Sent out packet with id {packet.id} belonging to flow {packet.flow_id}")

                            self.deficit[flow_id] -= packet.size

                            # Remove a packet from its queue
                            self.flow_queue_count[flow_id] -= 1

                            if self.flow_queue_count[flow_id] == 0:
                                self.deficit[flow_id] = 0.0
                        else:
                            # Put the packet back into the queue but keep it head-of-line
                            assert not flow_id in self.head_of_line
                            self.head_of_line[flow_id] = packet
                            break

            yield self.env.timeout(1.0 / self.rate)


    def put(self, pkt):
        self.packets_rec += 1
        flow_id = pkt.flow_id
        self.flow_queue_count[flow_id] += 1

        if self.debug:
            print("Time = {}, Flow id = {}, packet_id = {}, deficit = {}"
                .format(self.env.now, flow_id, pkt.id, self.deficit[flow_id]))

        if not flow_id in self.stores:
            self.stores[flow_id] = simpy.Store(self.env)

        return self.stores[flow_id].put(pkt)
