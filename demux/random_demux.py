from random import choices
"""
A demultiplexing element that chooses the output port at random.
"""
class RandomBrancher:
    """
    The constructor takes a list of output ports and a list of probabilities. 
    Use the output ports to connect to other network elements.

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
        self.n_ports = len(self.probs)
        self.outs = [None for i in range(self.n_ports)]  # Create and initialize output ports
        self.packets_rec = 0


    def put(self, pkt):
        self.packets_rec += 1
        choices(self.outs, weights=self.probs)[0].put(pkt)
