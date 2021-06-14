from utils import stampedstore

class VirtualClockServer:
    """ Models a virtual clock server. For theory and implementation see:
        L. Zhang, Virtual clock: A new traffic control algorithm for packet switching networks,
        in ACM SIGCOMM Computer Communication Review, 1990, vol. 20, pp. 19.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        rate : float
            the bit rate of the port
        vticks : A list
            list of the vtick parameters (for each possible packet flow_id). We assume a simple assignment of
            flow id to vticks, i.e., flow_id = 0 corresponds to vticks[0], etc... We assume that the vticks are
            the inverse of the desired rates for the flows in bits per second.
    """
    def __init__(self, env, rate, vticks, debug=False):
        self.env = env
        self.rate = rate
        self.vticks = vticks
        self.auxVCs = [0.0 for i in range(len(vticks))]  # Initialize all the auxVC variables
        self.out = None
        self.packets_rec = 0
        self.packets_dropped = 0
        self.debug = debug
        self.store = stampedstore.StampedStore(env)
        self.action = env.process(self.run())  # starts the run() method as a SimPy process


    def run(self):
        while True:
            packet = (yield self.store.get())
            # Send message
            yield self.env.timeout(msg.size*8.0/self.rate)
            self.out.put(packet)


    def put(self, pkt):
        self.packets_rec += 1
        now = self.env.now
        flow_id = pkt.flow_id
        # Update of auxVC for the flow. We assume that vticks is the desired bit time
        # i.e., the inverse of the desired bits per second data rate.
        # Hence we then multiply this value by the size of the packet in bits.
        self.auxVCs[flow_id] = max(now, self.auxVCs[flow_id]) + self.vticks[flow_id]*pkt.size*8.0
        # Lots of work to do here to implement the queueing discipline
        return self.store.put((self.auxVCs[flow_id], pkt))
