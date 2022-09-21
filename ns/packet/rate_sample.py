#TODO: .newly_lost, what's the difference between lost?

class RateSample:
    """
    The class rate sample used for estimation of delivery rate
    Y. Cheng, N. Cardwell, S. Hassas Yeganeh, V.Jacvobson 
    draft-cheng-iccrg-delivery-rate-estimation-02
    """
    def __init__(self):
        self.delivery_rate = 0
        self.delivered = 0
        self.prior_delivered = 0
        self.prior_time = 0
        self.newly_acked = 0
        self.last_acked = 0
        self.delivery_rate = 0
        self.send_rate = 0
        self.ack_rate = 0
        self.interval = 0
        self.ack_elapsed = 0
        self.send_elapsed = 0
        self.minRTT = 10
        self.rtt = -1
        self.lost = 0
        self.is_app_limited = False
        self.newly_lost = 0
        self.full_lost = 0
        self.prior_lost = 0
        self.tx_in_flight = -1
        
    def send_packet(self, packet, C, packets_in_flight, current_time):
        if (packets_in_flight == 0):
            C.first_sent_time = current_time
            C.delivered_time  = current_time
        packet.first_sent_time = C.first_sent_time
        packet.delivered_time = C.delivered_time
        packet.delivered = C.delivered
        packet.lost = C.lost
        packet.is_app_limited = (C.is_app_limited != 0)
        
    def updaterate_sample(self, packet, C ,current_time):
        if packet.delivered_time == 0:
            return # packet already sacked
        C.delivered += packet.size
        C.delivered_time = current_time
        if (packet.delivered >= self.prior_delivered):
            self.prior_delivered = packet.delivered
            if not packet.self_lost:
                self.send_elapsed = packet.time - packet.first_sent_time
                self.ack_elapsed = C.delivered_time - packet.delivered_time
                self.prior_time = packet.delivered_time
            self.is_app_limited = packet.is_app_limited
            self.tx_in_flight = packet.tx_in_flight
            C.first_sent_time = packet.time
        
        packet.delivered_time = 0

    def update_sample_group(self, C, minRTT = -1):
        self.rtt = minRTT
        self.newly_lost = C.lost - self.prior_lost
        self.prior_lost = C.lost
        # print(f"BBRS ack_elpased{self.ack_elapsed}, send_elapsed{self.send_elapsed}")
        if(C.is_app_limited and C.delivered > C.is_app_limited):
                C.is_app_limited = 0
        
        self.minRTT = minRTT
        self.delivered = C.delivered - self.prior_delivered
        self.interval = max(self.ack_elapsed, self.send_elapsed)
        if(self.interval < self.minRTT):
            self.interval = -1
            return False
        self.delivery_rate = self.delivered / self.interval
        # print(f"BBRState interval {self.interval}, rtt {self.minRTT}, delivered {self.delivered}, {self.prior_delivered} {self.prior_time} delivery_rate {self.delivery_rate}")
        return True

class Connection:
    def __init__(self):
        self.is_app_limited = 0
        self.first_sent_time = 0
        self.delivered = 0
        self.delivered_time = 0
        self.lost = 0
        self.pipe = 0 # How to estimate
        self.lost_out = 0
        self.retrans_out = 0
        self.is_cwnd_limited = False
        self.write_seq = 0
        self.pending_trans = 0 # In our simulation, this will always be 0
        
    
    def mark_connection_app_limited(self, packets_in_flight):
        #self.is_app_limited = (self.delivered + packets_in_flight) ? : 1
        if (self.delivered + packets_in_flight == 0): self.is_app_limited = 1
        else: self.is_app_limited = self.delivered + packets_in_flight
    
#     The sending application asks the transport layer to send more data; i.e., upon each write from the application, before new application data is enqueued in the transport send buffer or transmitted.
#     At the beginning of ACK processing, before updating the estimated number of packets in flight, and before congestion control modifies the cwnd or pacing rate.
#     At the beginning of connection timer processing, for all timers that might result in the transmission of one or more data segments. For example: RTO timers, TLP timers, RACK reordering timers, or Zero Window Probe timers.
    def check_if_application_limited(self, next, mss, packet_in_flight):
        """
            C.write_seq: The data sequence number one higher than that of the last octet queued for transmission in the transport layer write buffer. 
            C.pending_transmissions: The number of bytes queued for transmission on the sending host at layers lower than the transport layer 
            (i.e. network layer, traffic shaping layer, network device layer).
            C.lost_out: The number of packets in the current outstanding window that are marked as lost.
            C.retrans_out: The number of packets in the current outstanding window that are being retransmitted.
            C.pipe: The sender's estimate of the amount of data outstanding in the network (measured in octets or packets). This includes data packets in the current outstanding window that are being transmitted or retransmitted and have not been SACKed or marked lost
        """
        if (self.write_seq - next < mss and self.pending_trans == 0
            and not self.is_cwnd_limited and self.lost_out <= self.retrans_out):
            if self.delivered + packet_in_flight > 0 : self.is_app_limited = self.delivered + packet_in_flight
            else: self.is_app_limited = 1
