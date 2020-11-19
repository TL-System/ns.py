import random

class RandomBrancher:
    """ A demultiplexing element that chooses the output port at random.

        Contains a list of output ports of the same length as the probability list
        in the constructor.  Use these to connect to other network elements.

        Parameters
        ----------
        env : simpy.Environment
            the simulation environment
        probs : List
            list of probabilities for the corresponding output ports
    """
    def __init__(self, env, probs):
        self.env = env

        self.probs = probs
        self.ranges = [sum(probs[0:n+1]) for n in range(len(probs))]  # Partial sums of probs
        if self.ranges[-1] - 1.0 > 1.0e-6:
            raise Exception("Probabilities must sum to 1.0")
        self.n_ports = len(self.probs)
        self.outs = [None for i in range(self.n_ports)]  # Create and initialize output ports
        self.packets_rec = 0


    def put(self, pkt):
        self.packets_rec += 1
        rand = random.random()
        for i in range(self.n_ports):
            if rand < self.ranges[i]:
                if self.outs[i]:  # A check to make sure the output has been assigned before we put to it
                    self.outs[i].put(pkt)
                return
