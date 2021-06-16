import random

from ns.port.port import SwitchPort


class REDPort(SwitchPort):
    def __init__(self,
                 env,
                 rate,
                 qlimit,
                 limit_bytes,
                 zero_downstream_buffer,
                 debug,
                 node_id,
                 max_threshold,
                 min_threshold,
                 max_probability,
                 weight_factor=9):
        super().__init__(env,
                         rate,
                         qlimit=qlimit,
                         limit_bytes=limit_bytes,
                         zero_downstream_buffer=zero_downstream_buffer,
                         debug=debug,
                         node_id=node_id)
        self.max_probability = max_probability
        self.max_threshold = max_threshold
        self.min_threshold = min_threshold
        self.weight_factor = weight_factor
        self.average_queue_size = 0

    def put(self, packet):
        """ Sends the packet 'pkt' to the next-hop element. """
        self.packets_rec += 1
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
                print(
                    f"Avg queue size ({self.average_queue_size}) exceeds threshold ({self.qlimit})"
                )
        elif self.average_queue_size >= self.max_threshold:
            rand = random.uniform(0, 1)
            if rand <= self.max_probability:
                self.packets_dropped += 1
                if self.debug:
                    print(
                        f"Avg queue size ({self.average_queue_size}) exceeds threshold ({self.qlimit})",
                        f"Packet dropped with probability {self.max_probability}"
                    )
            else:
                self.byte_size += packet.size
                if self.zero_downstream_buffer:
                    self.downstream_store.put(packet)
                return self.store.put(packet)
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
                self.byte_size += packet.size
                if self.zero_downstream_buffer:
                    self.downstream_store.put(packet)
                return self.store.put(packet)
        else:
            self.byte_size += packet.size

            if self.zero_downstream_buffer:
                self.downstream_store.put(packet)

            return self.store.put(packet)
