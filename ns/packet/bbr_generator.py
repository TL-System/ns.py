"""
Implements a packet generator that simulates the TCP protocol, including support for
various congestion control mechanisms.
"""
import copy

import simpy

from ns.packet.packet import Packet
from ns.packet.rate_sample import Connection, RateSample
from ns.utils.timer import Timer


class BBRPacketGenerator:
    """Generates packets with a simulated TCP protocol.

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

    def __init__(
        self,
        env,
        flow,
        cc,
        element_id=None,
        rtt_estimate=0.14,
        granularity=0.01,
        debug=True,
    ):
        self.element_id = element_id
        self.env = env
        self.out = None
        self.flow = flow
        self.granularity = granularity
        self.congestion_control = cc
        self.congestion_control.rs = RateSample()
        self.congestion_control.C = Connection()
        self.packet_in_flight = 0

        self.mss = 512  # maximum segment size, in bytes
        self.last_arrival = 0  # the time when data last arrived from the flow

        # the next sequence number to be sent, in bytes
        self.next_seq = 0
        # the maximum sequence number in the in-transit data buffer
        self.send_buffer = self.flow.init_send_buffer()
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

        # the in-flight packets (segments)
        self.sent_packets = {}

        self.timer = None
        self.to_pkt_id = 0

        self.action = env.process(self.run())
        self.debug = debug

    def update_next_seq(self):
        self.send_buffer += self.flow.next_send_buffer(self.env.now)
        self.congestion_control.C.write_seq = self.send_buffer + 1
        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

    def run(self):
        # FIle download, video, game
        """The generator function used in simulations."""
        if self.flow.start_time:
            yield self.env.timeout(self.flow.start_time)

        while self.env.now < self.flow.finish_time:
            if self.flow.size is not None and self.next_seq >= self.flow.size:
                return

            while self.next_seq >= self.send_buffer:
                # retrieving more packets from the (application-layer) flow
                if self.flow.arrival_dist is not None:
                    # if the flow has an arrival distribution, wait for the next arrival
                    wait_time = self.flow.arrival_dist() - (
                        self.env.now - self.last_arrival
                    )
                    if wait_time > 0:
                        yield self.env.timeout(wait_time)

            self.update_next_seq()
            # the sender can transmit up to the size of the congestion window
            if self.env.now - self.congestion_control.next_departure_time < 0:
                yield self.env.timeout(
                    self.congestion_control.next_departure_time - self.env.now
                )
            if self.next_seq + self.mss > min(
                self.send_buffer, self.last_ack + self.congestion_control.cwnd
            ):
                self.congestion_control.C.is_cwnd_limited = True
                yield self.cwnd_available.get()
            else:
                packet = Packet(
                    self.env.now,
                    self.mss,
                    self.next_seq,
                    src=self.flow.src,
                    flow_id=self.flow.fid,
                    tx_in_flight=self.packet_in_flight,
                )
                self.congestion_control.rs.send_packet(
                    packet,
                    self.congestion_control.C,
                    self.max_ack - self.next_seq,
                    self.env.now,
                )
                self.congestion_control.next_departure_time = self.env.now
                if self.congestion_control.pacing_rate > 0:
                    self.congestion_control.next_departure_time += (
                        packet.size / self.congestion_control.pacing_rate
                    )

                self.sent_packets[packet.packet_id] = packet
                self.packet_in_flight += packet.size
                if self.debug:
                    print(
                        "Send packet {:d} with size {:d}, "
                        "flow_id {:d} at time {:.4f}, delivered_time {:.4f}.".format(
                            packet.packet_id,
                            packet.size,
                            packet.flow_id,
                            self.env.now,
                            packet.delivered_time,
                        )
                    )
                assert packet.delivered_time > 0
                self.out.put(packet)

                self.next_seq += packet.size

                self.congestion_control.C.check_if_application_limited(
                    self.next_seq, self.mss, self.packet_in_flight
                )

                if self.timer is None:
                    self.timer = Timer(self.env, 0, self.timeout_callback, self.rto)
                    self.to_pkt_id = packet.packet_id

                if self.debug:
                    print(
                        "Setting a timer for packet {:d} with an RTO"
                        " of {:.4f}.".format(packet.packet_id, self.rto)
                    )

    def timeout_callback(self, packet_id=0):
        """To be called when a timer expired for a packet with 'packet_id'."""
        self.update_next_seq()
        packet_id = self.max_ack
        if self.debug:
            print(
                "Timer expired for packet {:d} {:d} at time {:.4f}.".format(
                    packet_id, self.flow.fid, self.env.now
                )
            )

        self.congestion_control.C.lost += self.sent_packets[packet_id].size
        self.sent_packets[packet_id].self_lost = True

        self.congestion_control.set_before_control(self.env.now, self.packet_in_flight)
        self.congestion_control.timer_expired(self.sent_packets[packet_id])

        # retransmitting the segment
        resent_pkt = self.sent_packets[packet_id]
        resent_pkt.time = self.env.now
        self.congestion_control.rs.send_packet(
            resent_pkt,
            self.congestion_control.C,
            self.max_ack - self.next_seq,
            self.env.now,
        )

        assert resent_pkt.delivered_time > 0
        self.out.put(resent_pkt)
        self.rto *= 2
        if self.rto > 60:
            self.rto = 60
        if self.debug:
            print(
                "to Resending packet {:d} with flow_id {:d} at time {:.4f} with a timeout time {:4f}.".format(
                    resent_pkt.packet_id,
                    resent_pkt.flow_id,
                    self.env.now,
                    self.env.now + self.rto,
                )
            )

        # starting a new timer for this segment and doubling the retransmission timeout
        self.timer.restart(self.rto)

        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

    def put(self, ack):
        """On receiving an acknowledgment packet."""
        self.update_next_seq()
        self.congestion_control.C.check_if_application_limited(
            self.next_seq, self.mss, self.packet_in_flight
        )

        sample_rtt = self.env.now - ack.time
        self.congestion_control.rs.newly_acked = ack.ack - self.last_ack

        if ack.ack == self.last_ack:
            temp_pkt = copy.copy(ack)
            temp_pkt.size = self.mss

            self.congestion_control.rs.updaterate_sample(
                temp_pkt, self.congestion_control.C, self.env.now
            )
            self.congestion_control.rs.update_sample_group(
                self.congestion_control.C, sample_rtt
            )
            if ack.ack < self.next_seq:
                self.dupack += 1
        else:
            # fast recovery in RFC 2001 and TCP Reno
            self.congestion_control.dupack_over()
            self.dupack = 0

        # RFC 6298 Update on rto
        if self.max_ack == 0:
            self.rtt_estimate = sample_rtt
            self.est_deviation = sample_rtt / 2
            self.rto = min(
                self.rtt_estimate + max(4 * self.est_deviation, self.granularity), 60
            )
            self.rto = max(self.rto, 1)
        else:
            sample_err = self.rtt_estimate - sample_rtt
            self.est_deviation = (3 * self.est_deviation + sample_err) / 4
            self.rtt_estimate = (7 * self.rtt_estimate + sample_rtt) / 8
            self.rto = min(
                self.rtt_estimate + max(4 * self.est_deviation, self.granularity), 60
            )
            self.rto = max(self.rto, 1)

        self.max_ack = max(self.max_ack, ack.ack)

        if ack.packet_id == self.to_pkt_id and self.max_ack < self.next_seq:
            self.timer.restart(self.rto, self.sent_packets[self.max_ack].time)

        if self.dupack == 2:
            self.congestion_control.C.lost += self.sent_packets[ack.ack].size

            self.sent_packets[ack.ack].self_lost = True

            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight
            )
            self.congestion_control.consecutive_dupacks_received(
                self.sent_packets[ack.ack]
            )
            self.congestion_control.ack_received(sample_rtt)

            resent_pkt = self.sent_packets[ack.ack]
            resent_pkt.time = self.env.now
            self.congestion_control.rs.send_packet(
                resent_pkt,
                self.congestion_control.C,
                self.max_ack - self.next_seq,
                self.env.now,
            )
            assert resent_pkt.delivered_time > 0
            # self.congestion_control.next_departure_time = self.env.now
            # if(self.congestion_control.pacing_rate > 0):
            #     self.congestion_control.next_departure_time += resent_pkt.size / self.congestion_control.pacing_rate

            if self.debug:
                print(
                    "dup Resending packet {:d} with flow_id {:d} at time {:.4f}.".format(
                        resent_pkt.packet_id, resent_pkt.flow_id, self.env.now
                    )
                )
            self.out.put(resent_pkt)

        elif self.dupack > 2:
            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight
            )
            self.congestion_control.ack_received(sample_rtt)
            self.congestion_control.more_dupacks_received(self.sent_packets[ack.ack])

        elif self.dupack == 0:
            self.congestion_control.set_before_control(
                self.env.now, self.packet_in_flight
            )

            temp_pkt = copy.copy(ack)
            temp_pkt.size = self.mss
            self.congestion_control.rs.updaterate_sample(
                temp_pkt, self.congestion_control.C, self.env.now
            )

            bbr_update = False
            if ack.packet_id in self.sent_packets:
                # temp_pkt = copy.copy(ack)
                # temp_pkt.size = self.mss
                # self.congestion_control..updaterate_sample(temp_pkt, self.congestion_control.C, self.env.now)
                bbr_update = True
                self.packet_in_flight -= self.sent_packets[ack.packet_id].size
                self.sent_packets[ack.packet_id].delivered_time = 0
                self.sent_packets[ack.packet_id].self_lost = False

            for i in range(self.max_ack, ack.ack, self.mss):
                if i in self.sent_packets.keys():
                    if self.sent_packets[i].delivered_time:
                        self.packet_in_flight -= self.sent_packets[i].size
                    self.congestion_control.rs.updaterate_sample(
                        self.sent_packets[i], self.congestion_control.C, self.env.now
                    )
                    del self.sent_packets[i]

            self.congestion_control.rs.update_sample_group(
                self.congestion_control.C, sample_rtt
            )

            self.congestion_control.rs.full_lost = 0
            last_packet_lost = -self.mss * 2

            for id, packet in self.sent_packets.items():
                if packet.self_lost:
                    if id - last_packet_lost > self.mss:
                        self.congestion_control.rs.full_lost += 1
                    last_packet_lost = id

            if ack.ack > self.max_ack:
                self.max_ack = ack.ack

            self.last_ack = ack.ack

            if self.debug:
                print(
                    "Ack received till sequence number {:d} at time {:.4f}.".format(
                        ack.ack, self.env.now
                    )
                )
                print(
                    "Congestion window size = {:.1f}, last ack = {:d}.".format(
                        self.congestion_control.cwnd, self.last_ack
                    )
                )

            if bbr_update:
                self.congestion_control.ack_received(sample_rtt)

            if self.max_ack == self.next_seq and self.timer is not None:
                self.timer.stop()
                del self.timer
                self.timer = None

            self.congestion_control.C.is_cwnd_limited = False
            self.cwnd_available.put(True)
