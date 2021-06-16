"""
Models an output port on a switch with a given rate and buffer size (in either bytes
or the number of packets), using the Early Random Detection (RED) mechanism to drop packets.
"""
import random

from ns.port.port import Port


class REDPort(Port):
    """ Models an output port on a switch with a given rate and buffer size (in either bytes
        or the number of packets), using the Early Random Detection (RED) mechanism to drop packets.

        Parameters
        ----------
        env: simpy.Environment
            the simulation environment
        rate: float
            the bit rate of the port
        element_id: int
            the element id of this port
        qlimit: integer (or None)
            a buffer size limit in bytes or packets for the queue (including items
            in service).
        limit_bytes: bool
            if true, the queue limit will be based on bytes if false the queue limit
            will be based on packets.
        zero_downstream_buffer: bool
            if true, assume that the downstream element does not have any buffers,
            and backpressure is in effect so that all waiting packets queue up in this
            element's buffer.
        debug: bool
            if true, print more debugging information.
    """
    def __init__(self,
                 env,
                 rate: float,
                 max_threshold: int,
                 min_threshold: int,
                 max_probability: float,
                 weight_factor: int = 9,
                 element_id: int = None,
                 qlimit: int = None,
                 limit_bytes: bool = True,
                 zero_downstream_buffer: bool = False,
                 debug: bool = False):

        super().__init__(env,
                         rate,
                         element_id=element_id,
                         qlimit=qlimit,
                         limit_bytes=limit_bytes,
                         zero_downstream_buffer=zero_downstream_buffer,
                         debug=debug)
        self.max_probability = max_probability
        self.max_threshold = max_threshold
        self.min_threshold = min_threshold
        self.weight_factor = weight_factor
        self.average_queue_size = 0

    def put(self, pkt):
        """ Sends the packet 'pkt' to this element. """
        self.packets_received += 1

        if self.limit_bytes:
            current_queue_size = self.byte_size
        else:
            current_queue_size = len(self.store.items)

        alpha = 2**-self.weight_factor
        self.average_queue_size = self.average_queue_size * (
            1 - alpha) + current_queue_size * alpha

        if self.average_queue_size >= self.qlimit:
            self.packets_dropped += 1
            if self.debug:
                print(f"Average queue size ({self.average_queue_size}) "
                      f"exceeds threshold ({self.qlimit})")
        elif self.average_queue_size >= self.max_threshold:
            rand = random.uniform(0, 1)
            if rand <= self.max_probability:
                self.packets_dropped += 1
                if self.debug:
                    print(
                        f"Avg queue size ({self.average_queue_size}) "
                        f"exceeds threshold ({self.qlimit})",
                        f"Packet dropped with probability {self.max_probability}"
                    )
            else:
                self.byte_size += pkt.size
                if self.zero_downstream_buffer:
                    self.downstream_store.put(pkt)
                return self.store.put(pkt)
        elif self.average_queue_size >= self.min_threshold:
            prob = (self.average_queue_size - self.min_threshold) / (
                self.max_threshold - self.min_threshold) * self.max_probability
            rand = random.uniform(0, 1)
            if rand <= prob:
                self.packets_dropped += 1
                if self.debug:
                    print(
                        f"Avg queue size ({self.average_queue_size}) exceeds min threshold",
                        f"Packet dropped with probability {prob}")
            else:
                self.byte_size += pkt.size
                if self.zero_downstream_buffer:
                    self.downstream_store.put(pkt)
                return self.store.put(pkt)
        else:
            self.byte_size += pkt.size

            if self.zero_downstream_buffer:
                self.downstream_store.put(pkt)

            return self.store.put(pkt)
