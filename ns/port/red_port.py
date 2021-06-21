"""
Implements a port with an output buffer, given an output rate and a buffer size (in either bytes
or the number of packets). This implementation uses the Random Early Detection (RED) mechanism to
drop packets.

This element can set the rate of the output port and an upper limit for the average queue size
(in bytes or the number of packets), and it keeps track of the number packets received and dropped.

Reference:

QoS: Congestion Avoidance Configuration Guide, Cisco IOS XE 17

https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/qos_conavd/configuration/xe-17/qos-conavd-xe-17-book/qos-conavd-xe-16-8-book_chapter_01.html
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
            The upper limit for the average queue length, beyond which all packets will
            be dropped. The queue length can be measured in bytes or packets, and includes
            the packet in service.
        max_threshold: integer
            The maximum (average) queue length threshold, beyond which packets will be
            dropped at the maximum probability.
        min_threshold: integer
            The minimum (average) queue length threshold to start dropping packets. This
            threshold should be set high enough to maximize the link utilization. If the
            minimum threshold is too low, packets may be dropped unnecessarily, and the
            transmission link will not be fully used.
        max_probability: float
            The maximum probability (which is equivalent to 1 / mark probability denominator)
            is the fraction of packets dropped when the average queue length is at the
            maximum threshold, which is 'max_threshold'. The rate of packet drop increases
            linearly as the average queue length increases, until the average queue length
            reaches the maximum threshold, 'max_threshold'. All packets will be dropped when
            'qlimit' is exceeded.
        weight_factor: float
            The exponential weight factor 'n' for computing the average queue size.
            average = (old_average * (1-1/2^n)) + (current_queue_size * 1/2^n)
        limit_bytes: bool
            if True, the queue length limits will be based on bytes; if False, the queue
            length limits will be based on packets.
        zero_downstream_buffer: bool
            if True, assume that the downstream element does not have any buffers,
            and backpressure is in effect so that all waiting packets queue up in this
            element's buffer.
        debug: bool
            If True, prints more verbose debug information.
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
                 limit_bytes: bool = False,
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

    def put(self, packet):
        """ Sends a packet to this element. """
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
                print(f"The average queue length {self.average_queue_size} "
                      f"exceeds the upper limit {self.qlimit}.")
        elif self.average_queue_size >= self.min_threshold:
            rand = random.uniform(0, 1)
            if rand <= self.max_probability:
                self.packets_dropped += 1
                if self.debug:
                    print(
                        f"The average queue length ({self.average_queue_size}) "
                        f"exceeds the maximum threshold ({self.qlimit}), ",
                        f"packet dropped with probability {self.max_probability}"
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
                        f"The average queue length {self.average_queue_size} "
                        f"exceeds the minimum threshold {self.min_threshold}, "
                        f"packet dropped with probability {prob}.")
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
