"""
Implements a packet generator that simulates the TCP protocol, including support for
various congestion control mechanisms.
"""
#Unit: bytes, second
import simpy

from ns.packet.packet import Packet
from ns.utils.timer import Timer
from ns.packet.rate_sample import RateSample, Connection


class TCPPacketGenerator:
    """ Generates packets with a simulated TCP protocol.

        Parameters
        ----------
        env: simpy.Environment
            The simulation environment.
        flow: Flow
            The flow that serves as the source (eventually, this should be a list).
        element_id: str
            The ID for this element.
        rec_flow: bool
            Are we recording the statistics of packets generated?
        rate_sample: RateSample
    """
    def __init__(self,
                 env,
                 flow,
                 cc,
                 element_id=None,
                 rtt_estimate=1,
                 debug=True):
        self.element_id = element_id
        self.env = env
        self.out = None
        self.flow = flow
        self.congestion_control = cc
        self.congestion_control.rs = RateSample()
        self.congestion_control.C = Connection()
        self.packet_in_flight = 0

        self.mss = 512  # maximum segment size, in bytes
        self.last_arrival = 0  # the time when data last arrived from the flow

        # the next sequence number to be sent, in bytes
        self.next_seq = 0
        # the maximum sequence number in the in-transit data buffer
        self.send_buffer = 0
        # the sequence number of the segment that is last acknowledged
        self.last_ack = 0
        # the maximum sequence number of the segment that is acknowledged 
        self.max_ack = 0
        # the count of duplicate acknolwedgments
        self.dupack = 0
        # the RTT estimate
        self.rtt_estimate = rtt_estimate
        # the retransmission timeout
        self.rto = self.rtt_estimate * 2
        # an estimate of the RTT deviation
        self.est_deviation = 0
        # whether or not space in the congestion window is available
        self.cwnd_available = simpy.Store(env)

        # the timers, one for each in-flight packets (segments) sent
        self.timers = {}
        # the in-flight packets (segments)
        self.sent_packets = {}

        self.action = env.process(self.run())
        self.debug = debug

        self.cwnd_list = []

    def run(self):
        """ The generator function used in simulations. """
        if self.flow.start_time:
            yield self.env.timeout(self.flow.start_time)

        while self.env.now < self.flow.finish_time:
            if self.flow.size is not None and self.next_seq >= self.flow.size:
                return

            while self.next_seq >= self.send_buffer:
                # retrieving more packets from the (application-layer) flow
                if self.flow.arrival_dist is not None:
                    # if the flow has an arrival distribution, wait for the next arrival
                    wait_time = self.flow.arrival_dist() - (self.env.now -
                                                            self.last_arrival)
                    if wait_time > 0:
                        yield self.env.timeout(wait_time)
                    self.last_arrival = self.env.now

                packet_size = 0
                if self.flow.size_dist is not None:
                    packet_size = self.flow.size_dist()
                else:
                    if self.flow.size is not None:
                        packet_size = min(self.mss,
                                          self.flow.size - self.next_seq)
                    else:
                        packet_size = self.mss
                self.send_buffer += packet_size

            # the sender can transmit up to the size of the congestion window
            if self.next_seq + self.mss > min(
                    self.send_buffer,
                    self.last_ack + self.congestion_control.cwnd):
                self.congestion_control.C.is_cwnd_limited = True 
                yield self.cwnd_available.get()
            elif self.env.now - self.congestion_control.next_departure_time < 0:
                yield self.env.timeout(self.congestion_control.next_departure_time - self.env.now)
            else:   
                packet = Packet(self.env.now,
                                self.mss,
                                self.next_seq,
                                src=self.flow.src,
                                flow_id=self.flow.fid,
                                tx_in_flight=self.packet_in_flight)
                self.congestion_control.rs.send_packet(packet, self.congestion_control.C, self.packet_in_flight, self.env.now)
                self.congestion_control.next_departure_time = self.env.now
                print(f"Pacing rate {self.congestion_control.pacing_rate}")
                if(self.congestion_control.pacing_rate > 0):
                    self.congestion_control.next_departure_time += packet.size / self.congestion_control.pacing_rate
                print(f"flow_id {self.flow.fid}, Now time is {self.env.now}, Next depart time {self.congestion_control.next_departure_time}")
                self.sent_packets[packet.packet_id] = packet
                self.packet_in_flight += 1
                if self.debug:
                    print("Send packet {:d} with size {:d}, "
                          "flow_id {:d} at time {:.4f}.".format(
                              packet.packet_id, packet.size, packet.flow_id,
                              self.env.now))
                self.out.put(packet)

                self.next_seq += packet.size
                self.timers[packet.packet_id] = Timer(
                    self.env,
                    timer_id=packet.packet_id,
                    timeout_callback=self.timeout_callback,
                    timeout=self.rto)

                if self.debug:
                    print("Setting a timer for packet {:d} with an RTO"
                          " of {:.4f}.".format(packet.packet_id, self.rto))

    def timeout_callback(self, packet_id):
        """ To be called when a timer expired for a packet with 'packet_id'. """
        if self.debug:
            print("Timer expired for packet {:d} at time {:.4f}.".format(
                packet_id, self.env.now))
        
        if  not self.sent_packets[packet_id].self_lost:
            self.congestion_control.rs.newly_lost += self.sent_packets[packet_id].size
            for packet in self.sent_packets.values():
                packet.lost += self.sent_packets[packet_id].size
        
        self.sent_packets[packet_id].self_lost = True
        self.congestion_control.timer_expired(self.sent_packets[packet_id])

        # retransmitting the segment
        resent_pkt = self.sent_packets[packet_id]
        resent_pkt.time = self.env.now
        self.congestion_control.rs.send_packet(resent_pkt, self.congestion_control.C, self.packet_in_flight, self.env.now)
        self.congestion_control.next_departure_time = self.env.now
        if(self.congestion_control.pacing_rate > 0):
            self.congestion_control.next_departure_time += resent_pkt.size / self.congestion_control.pacing_rate
        self.out.put(resent_pkt)

        if self.debug:
            print("Resending packet {:d} with flow_id {:d} at time {:.4f}.".
                  format(resent_pkt.packet_id, resent_pkt.flow_id,
                         self.env.now))

        # starting a new timer for this segment and doubling the retransmission timeout
        self.rto *= 2
        self.timers[packet_id].restart(self.rto)

    def put(self, ack):

        """ On receiving an acknowledgment packet. """
        assert ack.flow_id >= 10000  # the received packet must be an ack

        if ack.ack == self.last_ack:
            self.dupack += 1
        else:
            # fast recovery in RFC 2001 and TCP Reno
            if self.dupack > 0:
                self.congestion_control.dupack_over()
                self.dupack = 0

        print(f"end ACK {ack.ack} {self.dupack} {ack.packet_id} {ack.flow_id}")

        sample_rtt = self.env.now - ack.time
        self.congestion_control.rs.newly_acked = 0
        for i in range(self.max_ack, ack.ack, self.mss):
            if i in self.sent_packets.keys() and not self.timers[i].stopped: 
                self.congestion_control.rs.updaterate_sample(self.sent_packets[i], self.congestion_control.C, self.env.now)
            
        self.congestion_control.rs.updaterate_sample(self.sent_packets[ack.packet_id], self.congestion_control.C, self.env.now)
            
        self.congestion_control.rs.update_sample_group(self.congestion_control.C, sample_rtt)

        self.congestion_control.rs.full_lost = 0
        last_packet_lost = False
        
        for packet in self.sent_packets.values():
            if packet.self_lost:
                if not last_packet_lost: self.congestion_control.rs.full_lost += 1
                last_packet_lost = False
            else: 
                last_packet_lost = False


        if self.dupack == 2:
            if  not self.sent_packets[ack.ack].self_lost:
                self.congestion_control.rs.newly_lost += self.sent_packets[ack.ack].size
                for packet in self.sent_packets.values():
                    packet.lost += self.sent_packets[ack.ack].size
        
            self.sent_packets[ack.ack].self_lost = True
            self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)
            self.congestion_control.ack_received(sample_rtt)
            self.congestion_control.consecutive_dupacks_received(self.sent_packets[ack.ack])

            resent_pkt = self.sent_packets[ack.ack]
            resent_pkt.time = self.env.now
            self.congestion_control.rs.send_packet(resent_pkt, self.congestion_control.C, self.packet_in_flight, self.env.now)
            self.congestion_control.next_departure_time = self.env.now
            if(self.congestion_control.pacing_rate > 0):
                self.congestion_control.next_departure_time += resent_pkt.size / self.congestion_control.pacing_rate
            if self.debug:
                print(
                    "Resending packet {:d} with flow_id {:d} at time {:.4f}.".
                    format(resent_pkt.packet_id, resent_pkt.flow_id,
                           self.env.now))

            self.out.put(resent_pkt)
            self.timers[ack.ack].restart(self.rto)

        elif self.dupack > 2:
            self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)
            self.congestion_control.ack_received(sample_rtt)
            self.congestion_control.more_dupacks_received(self.sent_packets[ack.ack])

            if self.last_ack + self.congestion_control.cwnd >= ack.ack and self.env.now > self.congestion_control.next_departure_time:
                resent_pkt = self.sent_packets[ack.ack]
                resent_pkt.time = self.env.now
                if self.debug:
                    print(
                        "Resending packet {:d} with flow_id {:d} at time {:.4f}."
                        .format(resent_pkt.packet_id, resent_pkt.flow_id,
                                self.env.now))
                self.congestion_control.rs.send_packet(resent_pkt, self.congestion_control.C, self.packet_in_flight, self.env.now)
                self.congestion_control.next_departure_time = self.env.now
                if(self.congestion_control.pacing_rate > 0):
                    self.congestion_control.next_departure_time += resent_pkt.size / self.congestion_control.pacing_rate
                self.out.put(resent_pkt)
                self.timers[ack.ack].restart(self.rto)

        elif self.dupack == 0:
            # new ack received, update the RTT estimate and the retransmission timout
            print(f"Rate sample is {self.congestion_control.rs.delivery_rate}")

            # Jacobsen '88: Congestion Avoidance and Control
            sample_err = sample_rtt - self.rtt_estimate
            self.rtt_estimate += 0.125 * sample_err
            self.est_deviation += 0.25 * (abs(sample_err) - self.est_deviation)
            self.rto = self.rtt_estimate + 4 * self.est_deviation

            self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)

            self.congestion_control.ack_received(sample_rtt)

            if(ack.ack > self.max_ack): 
                self.max_ack = ack.ack

            self.last_ack = ack.ack
            
            if self.debug:
                print("Ack received till sequence number {:d} at time {:.4f}.".
                      format(ack.ack, self.env.now))
                print(
                    "Congestion window size = {:.1f}, last ack = {:d}.".format(
                        self.congestion_control.cwnd, self.last_ack))
            
            self.congestion_control.C.is_cwnd_limited = False
            self.cwnd_available.put(True)
        
        print(self.congestion_control.state, self.env.now, self.congestion_control.pacing_rate, self.congestion_control.cwnd, self.element_id)

        for i in range(self.max_ack, ack.ack, self.mss):
            if i in self.timers:
                if not self.timers[i].stopped:
                    self.packet_in_flight -= 1
                    self.timers[i].stop()
                del self.timers[i]
                del self.sent_packets[i]

        if ack.packet_id in self.timers:
            if not self.timers[ack.packet_id].stopped:
                self.packet_in_flight -= 1
            self.timers[ack.packet_id].stop()
            self.sent_packets[ack.packet_id].self_lost = False
            
        self.congestion_control.rs.newly_lost = 0
        self.cwnd_list.append(self.congestion_control.cwnd)
