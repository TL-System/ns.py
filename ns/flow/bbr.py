"""
The TCP BBR congestion control algorithm, developed at Google in 2016.

Reference:

Neal Cardwell, Yuchung Cheng, C. Stephen Gunn, Soheil Hassas Yeganeh,
Van Jacobson "BBR Congestion control"
IETF 97: Seoul, Nov 2016
"""


# rs : newly_acked, delivery_rate, is_app_limited
# packet : delivered, size
# Remember packet.delievered = self.delievered when the package was sent
# C: the connection of the time
# packets_in_flight is something global?
# Code after one round-trip in fast recovery || upon exiting loss recovery

from smtplib import SMTP_SSL
from ns.flow.cc import CongestionControl
from enum import Enum
import random

class BBRState(Enum):
    STARTUP = 0
    DRAIN = 1
    PROBEBW = 2
    PROBERTT = 3

class BBRSemiState(Enum):
    PROBEBW_CRUISE = 0
    PROBEBW_REFILL = 1
    PROBEBW_UP = 2
    PROBEBW_DOWN = 3

class BBRAckStates(Enum):
    ACKS_PROBE_STARTING = 0
    ACKS_PROBE_FEEDBACK = 1
    ACKS_PROBE_STOPPING = 2
    ACKS_REFILLING = 3

class TCPBbr(CongestionControl):
    def __init__(self,
                 mss: int = 512,
                 cwnd: int = 512,
                 ssthresh: int = 65535,
                 inf: float = float("inf"),
                 debug: bool = False):
        super().__init__(mss, cwnd, ssthresh, debug)
        self.state = BBRState.STARTUP
        self.prior_cwnd = 0
        self.idle_restart = False
        self.rtprop = float('inf')
        self.round_count = 0
        self.round_start = False
        self.delievered = 0
        self.btl_bw = 0
        self.inf = inf
        self.next_round_delievered = 0
        self.BBRExtraAckedFilterLen = 10
        self.max_bw_vector = [0., 0.]
    
    def need_est_delivery_rate(self):
        return True
    
    def bbr_update_latest_delivery_signal(self, rs, C):
        self.loss_round_start = 0
        self.bw_latest = max(self.bw_latest, rs.delivery_rate)
        self.inflight_latest = max (self.inflight_latest, rs.delivered)
        if (rs.prior_delivered == self.loss_round_delivered):
            self.loss_round_delivered = C.delivered
            self.loss_round_start = 1

    def bbr_update_ack_aggregation(self, rs, current_time):
        interval = (current_time - self.extra_acked_interval_start)
        expected_delivered = self.bw * interval
        if (self.extra_acked_delivered <= expected_delivered):
            self.extra_acked_delivered = 0
            self.extra_acked_interval_start = current_time
            self.expected_delivered = 0
        self.extra_acked_delivered += rs.newly_acked
        self.extra = self.extra_acked_delivered - self.expected_delivered
        self.extra = min(self.expected_delivered, self.cwnd)
        self.extra_acked =  update_windowed_max_filter(
            filter=BBR.ExtraACKedFilter,
            value=extra,
            time=BBR.round_count,
            window_length=BBRExtraAckedFilterLen)
    
    def bbr_update_round(self, packet):
        self.delievered += packet.size # The packet is norma
        if (packet.delievered >= self.next_round_delievered):
            self.next_round_delievered = self.delievered
            self.round_count += 1
            self.round_start = True
        else:
            self.round_start = False

    def bbr_update_max_bw(self, packet, rs):
        self.bbr_update_round(packet)
        if (rs.delievery_rate >= self.btl_bw or not rs.is_app_limited):
            # self.btl_bw = update_windowed_max_filter(filter=BBR.MaxBwFilter,
            #           value=rs.delivery_rate,
            #           time=BBR.cycle_count,
            #           window_length=MaxBwFilterLen)
            max_bw_vector[self.cycle_count & 1] = rs.delievery_rate
            self.max_bw = max(max_bw_vector[0], max_bw_vector[1])
        # Max Bw Filter Len = 2

    def bbr_init_lower_bounds(self):
        if (self.bw_lo == self.inf):
            self.bw_lo = self.max_bw
        if (self.inflight_lo == self.inf):
            self.inflight_lo = self.cwnd
    
    def bbr_loss_lower_bounds(self):
        self.bw_lo = max(self.bw_latest, self.beta * self.bw_lo)
        self.inflight_lo = max(self.inflight_latest, self.beta * self.inflight_lo)

    def bbr_adapt_lower_bounds_from_congestion(self):
        if (self.state == BBRState.PROBEBW): 
            return
        if (self.loss_in_round > 0):
            self.bbr_init_lower_bounds()
            self.bbr_loss_lower_bounds()

    def bbr_update_congestion_signal(self, rs):
        self.bbr_update_max_bw()
        if(rs.losses > 0):
            self.loss_in_round = 1
        if (self.loss_in_round > 0):
            return #wait until the end of round trip
        self.bbr_adapt_lower_bounds_from_congestion()
        self.loss_in_round= 0

    def bbr_enter_startup(self):
        self.state = BBRState.STARTUP
        self.pacing_gain = BBRStartupPacingGain
        self.cwnd_gain = BBRStartupCWndGain    

    def bbr_check_startup_full_bw(self,rs):
        if (self.filled_pipe or not self.round_start or rs.is_app_limited):
            return
        if (self.max_bw >= self.full_bw * 1.25):
            self.full_bw = self.max_bw
            self.full_bw_cnt = 0
            return
        self.full_bw_cnt += 1
        if (self.full_bw_cnt >= 3):
            self.filled_pipe = True
    
    def bbr_check_startup_high_loss(self, rs):
        # No Gake Code
        # The connection has been in fast recovery for at least one full round trip.
        # The loss rate over the time scale of a single full round trip exceeds BBRLossThresh (2%).
        # There are at least BBRStartupFullLossCnt=3 discontiguous sequence ranges lost in that round trip.
        if (not self.in_fast_recovery):
            return
        if (rs.loss_rate > self.loss_thresh and BBRStartupFullLossCnt >= 3):
            self.filled_pipe = True

    def bbr_enter_drain(self):
        self.state = BBRState.DRAIN
        self.pacing_gain = 1/ self.bbr_startup_cwnd_gain
        self.cwnd_gain = self.bbr_startup_cwnd_gain

    def bbr_check_startup_done(self,rs):
        self.bbr_check_startup_full_bw(rs)
        self.bbr_check_startup_high_loss(rs)
        if (self.state == BBRState.STARTUP and self.filled_pipe):
            self.bbr_enter_drain()

    def bbr_bdp_multiple(self, gain):
        if (self.min_rtt == self.inf):
            return InitialCwnd
        self.bdp = self.bw * self.min_rtt
        return gain * self.bdp
    
    def bbr_quantization_budget(self, inflight):
        self.update_offload_budget()
        temp = max (inflight, self.offload_budget)
        temp  = max(temp, self.bbr_min_pipe_cwnd)
        if (self.state == BBRState.PROBEBW and self.cycle_idx == BBRSemiState.PROBEBW_UP):
            temp += 2
        return temp
    
    def bbr_inflight(self, gain):
        self.inflight = self.bbr_bdp_multiple(gain)
        return self.bbr_quantization_budget(self.inflight)

    def bbr_reset_congestion_signals(self):
        self.loss_in_round = 0
        self.bw_latest = 0
        self.inflight_latest = 0
    
    def bbr_start_round(self, C):
        self.next_round_delievered = C.delievered

    def bbr_pick_probe_wait(self):
        self.rounds_since_bw_probe = random.randint(0,1)
        self.bw_probe_wait = 2.0 + random.uniform(0.0, 1.0) #2.0 -> 2.0 sec

    def bbr_start_probebw_down(self, current_time):
        self.bbr_reset_congestion_signals()
        self.probe_up_cnt = self.inf
        self.bbr_pick_probe_wait()
        self.cycle_stamp = current_time
        self.ack_phase = BBRAckStates.ACKS_PROBE_STOPPING
        self.bbr_start_round()
        self.cycle_idx = BBRSemiState.PROBEBW_DOWN

    def bbr_enter_probebw(self):
        self.bbr_start_probebw_down()

    def bbr_check_drain(self):
        if (self.state == BBRState.DRAIN and packets_in_flight <= self.bbr_inflight(1.0)) :
            self.bbr_enter_probebw()
    
    def bbr_advance_max_bw_filter(self):
        self.cycle_count += 1
    
    def bbr_is_inflight_too_high(self, rs):
        return (rs.lost > rs.tx_in_flight * BBRLossThresh)

    def bbr_target_inflight(self):
        return min(self.bdp, self.cwnd)
        
    def bbr_handle_inflight_too_high(self, rs):
        self.bw_probe_samples = 0
        if (not rs.is_app_limited):
            self.inflight_hi = max(rs.tx_in_flight,
                self.bbr_target_inflight() * self.beta)
        if (self.cycle_idx == BBRSemiState.PROBEBW_UP):
            self.bbr_start_probebw_down()

    def bbr_check_inflight_too_high(self, rs):
        if (self.bbr_is_inflight_too_high(rs)):
            if (self.bw_probe_samples > 0):
                self.bbr_handle_inflight_too_high(rs)
            return True
        else:
            return False
    
    def bbr_raise_inflight_hi_slope(self):
        growth_this_round = MSS << self.bw_probe_up_rounds
        self.bw_probe_up_rounds = min(self.bw_probe_up_rounds + 1, 30)
        self.probe_up_cnt = max(self.cwnd // growth_this_round, 1)

    def bbr_probe_inflight_hi_upward(self,rs, C):
        if (not C.is_cwnd_limited or self.cwnd < self.inflight_hi):
            return
        self.bw_probe_up_acks += rs.newlu_acked
        if (self.bw_probe_up_acks >= self.probe_up_cnt):
            delta = self.bw_probe_up_acks / self.probe_up_cnt
            self.bw_probe_up_akcs -= delta * self.bw_probe_up_cnt
            self.inflight_hi += delta
        if (self.round_start):
            self.bbr_raise_inflight_hi_slope()

    def bbr_adapt_upper_bounds(self, rs):
        if (self.ack_phase == BBRAckStates.ACKS_PROBE_STARTING and self.round_start):
            self.ack_phase = BBRAckStates.ACKS_PROBE_FEEDBACK
        if (self.ack_phase == BBRAckStates.ACKS_PROBE_STOPPING and self.round_start):
            if (self.state == BBRState.PROBEBW and not rs.is_app_limited):
                self.bbr_advance_max_bw_filter()
        if (not self.bbr_check_inflight_too_high()):
            if (self.inflight_hi == self.inf or self.bw_hi == self.inf):
                return
            self.inflight_hi = max(self.inflight_hi, rs.tx_in_flight)
            self.bw_hi = max(rs.delievery_rate, self.bw_hi) # Fake code, rs.bw?
            if (self.cycle_idx == BBRSemiState.PROBEBW_UP):
                self.bbr_probe_inflight_hi_upward()
    
    def bbr_has_elapsed_in_phase(self, interval, current_time):
        return current_time > self.cycle_stamp + interval

    def bbr_is_reno_coexistence_probe_time(self):
        reno_rounds = self.bbr_target_inflight()
        rounds = min(reno_rounds, 63)
        return self.rounds_since_bw_probe >= rounds
    
    def bbr_reset_lower_bounds(self):
        self.bw_lo = self.inf
        self.inflight_lo = self.inf
    
    def bbr_start_probebw_refill(self):
        self.bbr_reset_lower_bounds()
        self.bw_probe_up_rounds = 0
        self.bw_probe_up_acks = 0
        self.ack_phase = BBRAckStates.ACKS_REFILLING
        self.bbr_start_round()
        self.cycle_idx = BBRSemiState.PROBEBW_REFILL

    def bbr_check_time_to_probebw(self):
        if (self.bbr_has_elapsed_in_phase(self.bw_probe_wait) or self.bbr_is_reno_coexistence_probe_time()):
            self.bbr_start_probebw_refill()
            return True
        return False
    
    def bbr_inflight_with_headroom(self):
        if (self.inflight_hi == self.inf):
            return self.inf
        headroom=max(1, self.inflight_hi * BBRHeadroom)
        return max(self.inflight_hi - headroom, BBRMinPipeCwnd)

    def bbr_check_time_to_cruise(self):
        if (self.inflight > self.bbr_inflight_with_headroom()):
            return False
        if (self.inflight <= self.bbr_inflight(self.max_bw, 1.0)):
            return True
    
    def bbr_start_probebw_cruise(self):
        self.cycle_idx = BBRSemiState.PROBEBW_CRUISE

    def bbr_start_probebw_up(self, current_time):
        self.ack_phase = BBRAckStates.ACKS_PROBE_STARTING
        self.bbr_start_round()
        self.cycle_stamp = current_time
        self.cycle_idx = BBRSemiState.PROBEBW_UP
        self.bbr_raise_inflight_hi_slope()

    def bbr_update_probebw_cycle_phase(self):
        if (not self.filled_pipe):
            return
        self.bbr_adapt_upper_bounds()
        if (self.state != BBRState.PROBEBW):
            return
        if(self.cycle_idx == BBRSemiState.PROBEBW_DOWN):
            if (self.bbr_check_time_to_probebw()):
                return
            if (self.bbr_check_time_to_cruise()):
                self.bbr_start_probebw_cruise()
        elif (self.cycle_idx == BBRSemiState.PROBEBW_CRUISE):
            if (self.bbr_check_time_to_probebw()):
                return
        elif (self.cycle_idx == BBRSemiState.PROBEBW_REFILL):
            if (self.round_start):
                self.bw_probe_samples = 1
                self.bbr_start_probebw_up()
        elif (self.cycle_idx == BBRSemiState.PROBEBW_UP):
            if (self.bbr_has_elapsed_in_phase(self.min_rtt) and self.inflight > self.bbr_inflight(self.max_bw, 1.25)):
                self.bbr_start_probebw_down()

    def bbr_update_min_rtt(self, rs, current_time):
        self.probe_rtt_expired = current_time > self.probe_rtt_min_stamp + ProbeRTTInterval
        if (rs.rtt >= 0 or rs.rtt < self.probe_rtt_min_delay or self.probe_rtt_expired):
            self.probe_rtt_min_delay = rs.rtt
            self.probe_rtt_min_stamp = current_time
        
        min_rtt_expired = current_time > self.min_rtt_stamp + MinRTTFilterLen
        if(self.probe_rtt_min_delay < self.min_rtt or min_rtt_expired):
            self.min_rtt = self.probe_rtt_min_delay
            self.min_rtt_stamp = self.probe_rtt_min_stamp
    
    def bbr_enter_probertt(self):
        self.state = BBRState.PROBERTT
        self.pacing_gain = 1.0
        self.cwnd_gain = BBRProbeRTTCwndGain
    
    def bbr_save_cwnd(self):
        if (not self.bbr_in_loss_recovery() and self.state != BBRState.PROBERTT):
            return self.cwnd
        else:
            return max(self.prior_cwnd, cwnd)
    
    def bbr_restore_cwnd(self):
        self.cwnd = max(self.cwnd, self.prior_cwnd)
    
    def bbr_exit_probertt(self):
        self.bbr_reset_lower_bounds()
        if(self.filled_pipe):
            self.bbr_start_probebw_down()
            self.bbr_start_probebw_cruise()
        else:
            self.bbr_enter_startup()

    def bbr_check_probertt_done(self, current_time):
        if (self.probe_rtt_done_stamp !=0 and current_time > self.probe_rtt_done_stamp):
            self.probe_rtt_min_stamp = current_time
            self.bbr_restore_cwnd()
            self.bbr_exit_probertt() 

    def bbr_handle_probertt(self, C, current_time):
        C.mark_connection_app_limited()
        if (self.probe_rtt_done_stamp == 0 and packets_in_flight <= self.bbr_probertt_cwnd()):
            self.probe_rtt_done_stamp = current_time + ProbeRTTDuration
            self.probe_rtt_round_done = False
            self.bbr_start_round()
        elif (self.probe_rtt_done_stamp != 0):
            if (self.round_start):
                self.probe_rtt_round_done = True
            if (self.probe_rtt_round_done):
                self.bbr_check_probertt_done(current_time)
    
    def bbr_check_probertt(self, rs):
        if(self.state != BBRState.PROBERTT and self.probe_rtt_expired and not self.idle_restart):
            self.bbr_enter_probertt()
            self.bbr_save_cwnd()
            self.probe_rtt_done_stamp = 0
            self.ack_phase = BBRAckStates.ACKS_PROBE_STOPPING
            self.bbr_start_round()
        if (self.state == BBRState.PROBERTT):
            self.bbr_handle_probertt()
        if (rs.delivered > 0):
            self.idle_restart = False
    # Dream never fall Rain Forest
    def bbr_advance_latest_delivery_signal(self, rs):
        if (self.loss_round_start):
            self.bw_latest = rs.delivery_rate
            self.inflight_latest = rs.delivered
    
    def bbr_bound_bw_for_model(self):
        self.bw = min(self.max_bw, self.bw_lo, self.bw_hi)

    def bbr_update_model_and_state(self, rs, current_time):
    # """ Update BBR parameters upon the arrival of a new ACK """
        self.bbr_update_latest_delivery_signal(rs)
        self.bbr_update_congestion_signal()
        self.bbr_update_ack_aggregation()
        self.bbr_check_startup_done()
        self.bbr_check_drain()
        self.bbr_update_probebw_cycle_phase()
        self.bbr_update_min_rtt(rs,current_time)
        self.bbr_check_probertt()
        self.bbr_advance_latest_delivery_signal(rs)
        self.bbr_bound_bw_for_model()
    
    def bbr_set_pacing_rate(self):
        rate = self.pacing_gain * self.bw * (100 - BBRPacingMarginPercent) / 100
        if (self.filled_pipe or rate > self.pacing_rate):
            self.pacing_rate = rate
    
    def bbr_set_send_quantum(self):
        if (self.pacing_rate < 1.2): #Unit 1.2Mbps
            floor = 1 * SMSS 
        else:
            floor = 2 * SMSS 
        self.send_quantum = min(self.pacing_rate * 1, 64) #Unit ms, kBytes
        self.send_quantum = max(self.send_quantum, floor)
    
    def bbr_update_aggregation_budget(self,inflight):
        # No Pseudocode offered here
        return

    def bbr_update_max_inflight(self):
        self.bbr_update_aggregation_budget()
        inflight = self.bbr_bdp_multiple(self.cwnd_gain)
        inflight += self.extra_acked
        self.max_inflight = self.bbr_quantization_budget(inflight)

    def bbr_modulate_cwnd_for_recovery(self,rs):
        if(rs.newly_lost > 0):
            self.cwnd = max(self.cwnd - rs.newly_lost, 1)
        if (self.packet_conservation):
            self.cwnd = max(self.cwnd, packets_in_flight + rs.newly_acked)
    
    def bbr_probertt_cwnd(self):
        probe_rtt_cwnd = self.bbr_bdp_multiple(self.bw, BBRProbeRTTCwndGain)
        probe_rtt_cwnd = max(probe_rtt_cwnd, BBRMinPipeCwnd)
        return probe_rtt_cwnd

    def bbr_bound_cwnd_for_probertt(self):
        if(self.state == BBRState.PROBERTT):
            self.cwnd = min(self.cwnd, self.bbr_probertt_cwnd())
    
    def bbr_bound_cwnd_for_model(self):
        cap = self.inf
        if (self.state == BBRState.PROBEBW and self.cycle_idx != BBRSemiState.PROBEBW_CRUISE):
            cap = self.inflight_hi
        elif (self.state == BBRState.PROBERTT or self.cycle_idx == BBRSemiState.PROBEBW_CRUISE):
            cap = self.bbr_inflight_with_headroom()
        cap = min(cap, self.inflight_lo)
        cap = max(cap, BBRMinPipeCwnd)
        self.cwnd = min(self.cwnd, cap)

    def bbr_set_cwnd(self, rs, C):
        self.bbr_update_max_inflight()
        self.bbr_modulate_cwnd_for_recovery()
        if (not self.packet_conversation):
            if (self.filled_pipe):
                self.cwnd = min(self.cwnd + rs.newly_acked, self.max_inflight)
            elif (self.cwnd < self.max_inflight or C.delivered < InitialCwnd):
                self.cwnd += rs.newly_acked
            self.cwnd = max(self.cwnd, BBRMinPipeCwnd)
        self.bbr_bound_cwnd_for_probertt()
        self.bbr_bound_cwnd_for_model()

    def bbr_update_control_param(self):
        self.bbr_set_pacing_rate()
        self.bbr_set_send_quantum()
        self.bbr_set_cwnd()

    def ack_received(self, rtt: float = 0, current_time: float = 0):
        self.bbr_update_model_and_state(current_time)
        self.bbr_update_control_param()

        