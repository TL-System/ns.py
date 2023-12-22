"""
The TCP BBR congestion control algorithm, developed at Google in 2016.

Reference:

Neal Cardwell, Yuchung Cheng, Stephen Gunn, Soheil Hassas Yeganeh,
Van Jacobson, "BBR Congestion control"
IETF 97: Seoul, Nov 2016
"""

# self.rs: newly_acked, delivery_rate, is_app_limited
# self.C: the connection of the time
# self.packet_in_flight is something global?
# Code after one round-trip in fast recovery || upon exiting loss recovery

import random
from enum import Enum

from ns.flow.cc import CongestionControl


class BBRState(Enum):
    """
    The states maintained by BBR.
    """

    STARTUP = 0
    DRAIN = 1
    PROBEBW = 2
    PROBERTT = 3


class BBRSemiState(Enum):
    """
    The bandwidth probes maintained by BBR.
    """

    PROBEBW_CRUISE = 0
    PROBEBW_REFILL = 1
    PROBEBW_UP = 2
    PROBEBW_DOWN = 3


class BBRAckStates(Enum):
    """
    The acknowledgment types in BBR.
    """

    ACKS_PROBE_STARTING = 0
    ACKS_PROBE_FEEDBACK = 1
    ACKS_PROBE_STOPPING = 2
    ACKS_REFILLING = 3
    ACKS_INIT = 4


def update_windowed_max_filter(_filter, value, time, window_length):
    _filter[time % window_length] = value
    ret = 0

    for i in range(window_length):
        if ret < _filter[i]:
            ret = _filter[i]

    return ret


class BBR(CongestionControl):
    """The BBR congestion control algorithm."""

    def __init__(
        self,
        mss: int = 512,
        cwnd: int = 1 << 16,
        ssthresh: int = 65535,
        inf: float = float("inf"),
        debug: bool = False,
        rtt_estimate: float = 0.1,
    ):
        super().__init__(mss, cwnd, ssthresh, debug)
        self.bw_probe_samples = 0
        self.prior_cwnd = 0
        self.idle_restart = False
        self.rtprop = float("inf")
        self.round_count = 0
        self.cycle_count = 0
        self.round_start = False
        self.delivered = 0
        self.inf = inf
        self.next_round_delivered = 0
        self.BBRExtraAckedFilterLen = 10
        self.max_bw = 0
        self.bw_latest = 0
        self.bw = 0
        self.bw_lo = self.inf
        self.bw_hi = self.inf
        self.inflight_hi = self.inf
        self.inflight_lo = self.inf
        self.full_bw = 0
        self.full_bw_cnt = 0
        self.inflight_latest = 0
        self.loss_round_delivered = 0
        self.loss_in_round = 0
        self.extra_acked = 0
        self.extra_acked_interval_start = 0
        self.extra_acked_delivered = 0
        self.probe_rtt_expired = False
        self.probe_rtt_done_stamp = 0
        self.probe_rtt_min_stamp = 0
        self.probe_rtt_min_delay = self.inf
        self.min_rtt_stamp = 0
        self.min_rtt = self.inf
        self.packet_conservation = False
        self.BBRExtraAckedFilterLen = 10
        self.BBRStartupPacingGain = 2.77
        self.BBRStartupCwndGain = 2.0
        self.InitialCwnd = cwnd
        self.BBRLossThresh = 0.02
        self.BBRProbeRTTCwndGain = 0.5
        self.BBRMinPipeCwnd = 4 * mss
        self.current_time = None
        self.filled_pipe = False
        self.ProbeRTTInterval = 5  # should be 5 sec
        self.MinRTTFilterLen = 10  # should be 10 sec (?)
        self.ProbeRTTDuration = 0.2  # sec or 200ms
        self.BBRHeadroom = 0.15
        self.BBRPacingMarginPercent = 1
        self.packet_in_flight = 0
        self.MaxBwFilterLen = 2
        self.BBRMinPipeCwnd = 4 * mss
        self.BBRMaxBwFilter = {0: 0, 1: 0}
        self.offload_budget = 0
        self.cycle_idx = BBRSemiState.PROBEBW_CRUISE
        self.in_fast_recovery = False
        self.BBRExtraAckedFilter = {
            0: 0,
            1: 0,
            2: 0,
            3: 0,
            4: 0,
            5: 0,
            6: 0,
            7: 0,
            8: 0,
            9: 0,
        }
        self.state = BBRState.STARTUP
        self.pacing_rate = self.cwnd / rtt_estimate * self.BBRStartupPacingGain
        self.pacing_gain = self.BBRStartupPacingGain
        self.cwnd_gain = self.BBRStartupCwndGain
        self.beta = 0.7
        self.send_quantum = self.mss
        self.probe_up_cnt = self.inf
        self.ack_phase = BBRAckStates.ACKS_INIT

    def set_before_control(self, current_time, packet_in_flight=0):
        self.current_time = current_time
        self.packet_in_flight = packet_in_flight

    def bbr_set_pacing_rate_with_gain(self, gain):
        rate = gain * self.bw * (100 - self.BBRPacingMarginPercent) / 100
        if self.filled_pipe or rate > self.pacing_rate:
            self.pacing_rate = rate

    def bbr_handle_restart_from_idle(self):
        if self.packet_in_flight == 0 and self.C.is_app_limited:
            self.idle_restart = True
            self.extra_acked_interval_start = self.current_time
            if self.state == BBRState.PROBEBW:
                self.bbr_set_pacing_rate_with_gain(1.0)
            elif self.state == BBRState.PROBERTT:
                self.bbr_check_probertt_done()

    def bbr_update_offload_budget(self):
        self.offload_budget = 3 * self.send_quantum

    def bbr_update_latest_delivery_signal(self):
        self.loss_round_start = 0
        self.bw_latest = max(self.bw_latest, self.rs.delivery_rate)
        self.inflight_latest = max(self.inflight_latest, self.rs.delivered)
        if self.rs.prior_delivered == self.loss_round_delivered:
            self.loss_round_delivered = self.C.delivered
            self.loss_round_start = 1

    def bbr_update_ack_aggregation(self):
        # Comment: Significant difference between pseudo code and google code
        interval = self.current_time - self.extra_acked_interval_start
        expected_delivered = self.bw * interval
        if self.extra_acked_delivered <= expected_delivered:
            self.extra_acked_delivered = 0
            self.extra_acked_interval_start = self.current_time
            self.expected_delivered = 0
        self.extra_acked_delivered += self.rs.newly_acked
        extra = self.extra_acked_delivered - self.expected_delivered
        extra = min(extra, self.cwnd)
        self.extra_acked = update_windowed_max_filter(
            _filter=self.BBRExtraAckedFilter,
            value=extra,
            time=self.round_count,
            window_length=self.BBRExtraAckedFilterLen,
        )

    def bbr_update_round(self):
        self.round_start = False
        if self.rs.prior_delivered >= self.next_round_delivered:
            self.next_round_delivered = self.C.delivered
            self.round_count += 1
            self.round_count %= self.BBRExtraAckedFilterLen
            self.round_start = True

    def bbr_update_max_bw(self):
        self.bbr_update_round()
        if self.rs.delivery_rate >= self.max_bw or not self.rs.is_app_limited:
            self.max_bw = update_windowed_max_filter(
                _filter=self.BBRMaxBwFilter,
                value=self.rs.delivery_rate,
                time=self.cycle_count,
                window_length=self.MaxBwFilterLen,
            )

    def bbr_init_lower_bounds(self):
        if self.bw_lo == self.inf:
            self.bw_lo = self.max_bw
        if self.inflight_lo == self.inf:
            self.inflight_lo = self.cwnd

    def bbr_loss_lower_bounds(self):
        self.bw_lo = max(self.bw_latest, self.beta * self.bw_lo)
        self.inflight_lo = max(self.inflight_latest, self.beta * self.inflight_lo)

    def bbr_adapt_lower_bounds_from_congestion(self):
        if self.state == BBRState.PROBEBW:
            return
        if self.loss_in_round > 0:
            self.bbr_init_lower_bounds()
            self.bbr_loss_lower_bounds()

    def bbr_update_congestion_signal(self):
        self.bbr_update_max_bw()
        if self.rs.lost > 0:
            self.loss_in_round = 1
        if self.loss_in_round == 0:
            return  # wait until the end of round trip
        self.bbr_adapt_lower_bounds_from_congestion()
        self.loss_in_round = 0

    def bbr_enter_startup(self):
        self.state = BBRState.STARTUP
        self.pacing_gain = self.BBRStartupPacingGain
        self.cwnd_gain = self.BBRStartupCwndGain

    def bbr_check_startup_full_bw(self):
        # if (self.filled_pipe or not self.round_start or self.rs.is_app_limited):
        #     return
        if self.max_bw >= self.full_bw * 1.25:
            self.full_bw = self.max_bw
            self.full_bw_cnt = 0
            return
        self.full_bw_cnt += 1
        if self.full_bw_cnt >= 3:
            self.filled_pipe = True

    def bbr_check_startup_high_loss(self):
        # No Pseudo-code, of less significance
        if not self.in_fast_recovery:
            return
        loss_rate = self.rs.newly_lost * 100 / self.packet_in_flight
        BBRLossThresh = 2
        if loss_rate > BBRLossThresh and self.rs.full_lost >= 3:
            self.filled_pipe = True

    def bbr_enter_drain(self):
        self.state = BBRState.DRAIN
        self.pacing_gain = 1 / self.BBRStartupCwndGain
        self.cwnd_gain = self.BBRStartupCwndGain

    def bbr_check_startup_done(self):
        self.bbr_check_startup_full_bw()
        self.bbr_check_startup_high_loss()  # This is highly unassoc
        if self.state == BBRState.STARTUP and self.filled_pipe:
            self.bbr_enter_drain()

    def bbr_bdp_multiple(self, bw, gain):
        if self.min_rtt == self.inf:
            return self.InitialCwnd
        self.bdp = bw * self.min_rtt
        return gain * self.bdp

    def bbr_quantization_budget(self, inflight):
        self.bbr_update_offload_budget()
        inflight = max(inflight, self.offload_budget, self.BBRMinPipeCwnd)
        if self.state == BBRState.PROBEBW and self.cycle_idx == BBRSemiState.PROBEBW_UP:
            inflight += 2 * self.mss
        return inflight

    def bbr_inflight(self, gain, bw: float = 0):
        if bw == 0.0:
            bw = self.bw
        inflight = self.bbr_bdp_multiple(bw, gain)
        return self.bbr_quantization_budget(inflight)

    def bbr_reset_congestion_signals(self):
        self.loss_in_round = 0
        self.bw_latest = 0
        self.inflight_latest = 0

    def bbr_start_round(self):
        self.next_round_delivered = self.C.delivered

    def bbr_pick_probe_wait(self):
        self.rounds_since_bw_probe = random.randint(0, 1)
        self.bw_probe_wait = 2.0 + random.uniform(0.0, 1.0)

    def bbr_start_probebw_down(self):
        self.bbr_reset_congestion_signals()
        self.probe_up_cnt = self.inf
        self.bbr_pick_probe_wait()
        self.cycle_stamp = self.current_time
        self.ack_phase = BBRAckStates.ACKS_PROBE_STOPPING
        self.bbr_start_round()
        self.cycle_idx = BBRSemiState.PROBEBW_DOWN
        self.state = BBRState.PROBEBW
        self.pacing_gain = 0.9
        self.cwnd_gain = 2

    def bbr_enter_probebw(self):
        self.bbr_start_probebw_down()

    def bbr_check_drain(self):
        if self.state == BBRState.DRAIN and self.packet_in_flight <= self.bbr_inflight(
            1.0, self.full_bw
        ):
            self.bbr_enter_probebw()

    def bbr_advance_max_bw_filter(self):
        self.cycle_count += 1
        self.cycle_count %= self.MaxBwFilterLen

    def bbr_is_inflight_too_high(self):
        return self.rs.lost > self.rs.tx_in_flight * self.BBRLossThresh

    def bbr_target_inflight(self):
        self.bdp = self.bbr_inflight(1.0, min(self.max_bw, self.bw_lo))
        return min(self.bdp, self.cwnd)

    def bbr_handle_inflight_too_high(self):
        self.bw_probe_samples = 0
        if not self.rs.is_app_limited:
            self.inflight_hi = max(
                self.rs.tx_in_flight, self.bbr_target_inflight() * self.beta
            )
        if self.cycle_idx == BBRSemiState.PROBEBW_UP:
            self.bbr_start_probebw_down()

    def bbr_check_inflight_too_high(self):
        if self.bbr_is_inflight_too_high():
            if self.bw_probe_samples > 0:
                self.bbr_handle_inflight_too_high()
            return True
        else:
            return False

    def bbr_raise_inflight_hi_slope(self):
        growth_this_round = self.mss << self.bw_probe_up_rounds
        self.bw_probe_up_rounds = min(self.bw_probe_up_rounds + 1, 30)
        self.probe_up_cnt = max(self.cwnd // growth_this_round, 1)

    def bbr_probe_inflight_hi_upward(self):
        if not self.C.is_cwnd_limited or self.cwnd < self.inflight_hi:
            return
        self.bw_probe_up_acks += self.rs.newly_acked
        if self.bw_probe_up_acks >= self.probe_up_cnt:
            delta = self.bw_probe_up_acks / self.probe_up_cnt
            self.bw_probe_up_akcs -= delta * self.bw_probe_up_cnt
            self.inflight_hi += delta
        if self.round_start:
            self.bbr_raise_inflight_hi_slope()

    def bbr_adapt_upper_bounds(self):
        if self.ack_phase == BBRAckStates.ACKS_PROBE_STARTING and self.round_start:
            self.ack_phase = BBRAckStates.ACKS_PROBE_FEEDBACK
        if self.ack_phase == BBRAckStates.ACKS_PROBE_STOPPING and self.round_start:
            if self.state == BBRState.PROBEBW and not self.rs.is_app_limited:
                self.bbr_advance_max_bw_filter()
        if not self.bbr_check_inflight_too_high():
            if self.inflight_hi == self.inf or self.bw_hi == self.inf:
                return
            self.inflight_hi = max(self.inflight_hi, self.rs.tx_in_flight)
            self.bw_hi = max(self.rs.delivery_rate, self.bw_hi)
            if self.cycle_idx == BBRSemiState.PROBEBW_UP:
                self.bbr_probe_inflight_hi_upward()

    def bbr_has_elapsed_in_phase(self, interval):
        return self.current_time > self.cycle_stamp + interval

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
        self.pacing_gain = 1.0
        self.cwnd_gain = 2

    def bbr_check_time_to_probebw(self):
        if (
            self.bbr_has_elapsed_in_phase(self.bw_probe_wait)
            or self.bbr_is_reno_coexistence_probe_time()
        ):
            self.bbr_start_probebw_refill()
            return True
        return False

    def bbr_inflight_with_headroom(self):
        if self.inflight_hi == self.inf:
            return self.inf
        headroom = max(self.mss, self.inflight_hi * self.BBRHeadroom)
        return max(self.inflight_hi - headroom, self.BBRMinPipeCwnd)

    def bbr_check_time_to_cruise(self):
        if self.packet_in_flight > self.bbr_inflight_with_headroom():
            return False
        if self.packet_in_flight <= self.bbr_inflight(1.0, self.max_bw):
            return True
        return False

    def bbr_start_probebw_cruise(self):
        self.cycle_idx = BBRSemiState.PROBEBW_CRUISE
        self.pacing_gain = 1.0
        self.cwnd_gain = 2

    def bbr_start_probebw_up(self):
        self.ack_phase = BBRAckStates.ACKS_PROBE_STARTING
        self.bbr_start_round()
        self.cycle_stamp = self.current_time
        self.cycle_idx = BBRSemiState.PROBEBW_UP
        self.pacing_gain = 1.25
        self.cwnd_gain = 2
        self.bbr_raise_inflight_hi_slope()

    def bbr_update_probebw_cycle_phase(self):
        if not self.filled_pipe:
            return
        self.bbr_adapt_upper_bounds()
        if self.state != BBRState.PROBEBW:
            return
        if self.cycle_idx == BBRSemiState.PROBEBW_DOWN:
            if self.bbr_check_time_to_probebw():
                return
            if self.bbr_check_time_to_cruise():
                self.bbr_start_probebw_cruise()
        elif self.cycle_idx == BBRSemiState.PROBEBW_CRUISE:
            if self.bbr_check_time_to_probebw():
                return
        elif self.cycle_idx == BBRSemiState.PROBEBW_REFILL:
            if self.round_start:
                self.bw_probe_samples = 1
                self.bbr_start_probebw_up()
        elif self.cycle_idx == BBRSemiState.PROBEBW_UP:
            if self.bbr_has_elapsed_in_phase(
                self.min_rtt
            ) and self.packet_in_flight > self.bbr_inflight(1.25, self.max_bw):
                self.bbr_start_probebw_down()

    def bbr_update_min_rtt(self):
        self.probe_rtt_expired = self.current_time > (
            self.probe_rtt_min_stamp + self.ProbeRTTInterval
        )
        if self.rs.rtt > 0 and (
            self.rs.rtt < self.probe_rtt_min_delay or self.probe_rtt_expired
        ):
            self.probe_rtt_min_delay = self.rs.rtt
            self.probe_rtt_min_stamp = self.current_time

        min_rtt_expired = self.current_time > (
            self.min_rtt_stamp + self.MinRTTFilterLen
        )
        if self.probe_rtt_min_delay < self.min_rtt or min_rtt_expired:
            self.min_rtt = self.probe_rtt_min_delay
            self.min_rtt_stamp = self.probe_rtt_min_stamp

    def bbr_enter_probertt(self):
        self.state = BBRState.PROBERTT
        self.pacing_gain = 1.0
        self.cwnd_gain = self.BBRProbeRTTCwndGain

    def bbr_save_cwnd(self):
        if not self.in_fast_recovery and self.state != BBRState.PROBERTT:
            return self.cwnd
        else:
            return max(self.prior_cwnd, self.cwnd)

    def bbr_restore_cwnd(self):
        self.cwnd = max(self.cwnd, self.prior_cwnd)

    def bbr_exit_probertt(self):
        self.bbr_reset_lower_bounds()
        if self.filled_pipe:
            self.bbr_start_probebw_down()
            self.bbr_start_probebw_cruise()
        else:
            self.bbr_enter_startup()

    def bbr_check_probertt_done(self):
        if (
            self.probe_rtt_done_stamp != 0
            and self.current_time > self.probe_rtt_done_stamp
        ):
            self.probe_rtt_min_stamp = self.current_time
            self.bbr_restore_cwnd()
            self.bbr_exit_probertt()

    def bbr_handle_probertt(self):
        self.C.mark_connection_app_limited(self.packet_in_flight)
        if (
            self.probe_rtt_done_stamp == 0
            and self.packet_in_flight <= self.bbr_probertt_cwnd()
        ):
            self.probe_rtt_done_stamp = self.current_time + self.ProbeRTTDuration
            self.probe_rtt_round_done = False
            self.bbr_start_round()
        elif self.probe_rtt_done_stamp != 0:
            if self.round_start:
                self.probe_rtt_round_done = True
            if self.probe_rtt_round_done:
                self.bbr_check_probertt_done()

    def bbr_check_probertt(self):
        if (
            self.state != BBRState.PROBERTT
            and self.probe_rtt_expired
            and not self.idle_restart
        ):
            self.bbr_enter_probertt()
            self.bbr_save_cwnd()
            self.probe_rtt_done_stamp = 0
            self.ack_phase = BBRAckStates.ACKS_PROBE_STOPPING
            self.bbr_start_round()
        if self.state == BBRState.PROBERTT:
            self.bbr_handle_probertt()
        if self.rs.delivered > 0:
            self.idle_restart = False

    def bbr_advance_latest_delivery_signal(self):
        if self.loss_round_start:
            self.bw_latest = self.rs.delivery_rate
            self.inflight_latest = self.rs.delivered

    def bbr_bound_bw_for_model(self):
        # self.bw = min(self.max_bw, self.bw_lo, self.bw_hi)
        self.bw = min(self.max_bw, self.bw_lo, self.BBRMaxBwFilter[self.cycle_count])

    def bbr_update_model_and_state(self):
        # """ Update BBR parameteself.rs upon the arrival of a new ACK """
        self.bbr_update_latest_delivery_signal()
        self.bbr_update_congestion_signal()
        # self.bbr_update_ack_aggregation()
        self.bbr_check_startup_done()
        self.bbr_check_drain()
        self.bbr_update_probebw_cycle_phase()
        self.bbr_update_min_rtt()
        self.bbr_check_probertt()
        self.bbr_advance_latest_delivery_signal()
        self.bbr_bound_bw_for_model()

    def bbr_set_pacing_rate(self):
        rate = self.pacing_gain * self.bw * (100 - self.BBRPacingMarginPercent) / 100
        if self.filled_pipe or rate > self.pacing_rate:
            self.pacing_rate = rate

    def bbr_set_send_quantum(self):
        if self.pacing_rate < 150000:  # Unit 1.2Mbps
            floor = 1 * self.mss  # SMSS
        else:
            floor = 2 * self.mss  # SMSS
        self.send_quantum = min(self.pacing_rate / 1000, 64 * 1024)  # Unit ms, kBytes
        self.send_quantum = max(self.send_quantum, floor)

    def bbr_update_aggregation_budget(self):
        # No Pseudocode offered here
        # Github code: bbr_ack_aggregation_cwnd ?
        pass

    def bbr_update_max_inflight(self):
        self.bbr_update_aggregation_budget()
        inflight = self.bbr_bdp_multiple(self.bw, self.cwnd_gain)
        inflight += self.extra_acked
        self.max_inflight = self.bbr_quantization_budget(inflight)

    def bbr_modulate_cwnd_for_recovery(self):
        if self.rs.newly_lost > 0:
            self.cwnd = max(self.cwnd - self.rs.newly_lost, self.mss)
        if self.packet_conservation:
            self.cwnd = max(self.cwnd, self.packet_in_flight + self.rs.newly_acked)

    def bbr_probertt_cwnd(self):
        probe_rtt_cwnd = self.bbr_bdp_multiple(self.bw, self.BBRProbeRTTCwndGain)
        probe_rtt_cwnd = max(probe_rtt_cwnd, self.BBRMinPipeCwnd)
        return probe_rtt_cwnd

    def bbr_bound_cwnd_for_probertt(self):
        if self.state == BBRState.PROBERTT:
            self.cwnd = min(self.cwnd, self.bbr_probertt_cwnd())

    def bbr_bound_cwnd_for_model(self):
        cap = self.inf
        if (
            self.state == BBRState.PROBEBW
            and self.cycle_idx != BBRSemiState.PROBEBW_CRUISE
        ):
            cap = self.inflight_hi
        elif self.state == BBRState.PROBERTT or (
            self.state == BBRState.PROBEBW
            and self.cycle_idx == BBRSemiState.PROBEBW_CRUISE
        ):
            cap = self.bbr_inflight_with_headroom()
        cap = min(cap, self.inflight_lo)
        cap = max(cap, self.BBRMinPipeCwnd)
        self.cwnd = min(self.cwnd, cap)

    def bbr_set_cwnd(self):
        self.bbr_update_max_inflight()
        self.bbr_modulate_cwnd_for_recovery()
        if not self.packet_conservation:
            if self.filled_pipe:
                self.cwnd = min(self.cwnd + self.rs.newly_acked, self.max_inflight)
            elif self.cwnd < self.max_inflight or self.C.delivered < self.InitialCwnd:
                self.cwnd += self.rs.newly_acked
            self.cwnd = max(self.cwnd, self.BBRMinPipeCwnd)
        self.bbr_bound_cwnd_for_probertt()
        self.bbr_bound_cwnd_for_model()

    def bbr_update_control_param(self):
        self.bbr_set_pacing_rate()
        self.bbr_set_send_quantum()
        self.bbr_set_cwnd()

    def ack_received(self, rtt: float = 0):
        self.rs.rtt = rtt
        self.bbr_update_model_and_state()
        self.bbr_update_control_param()

    def bbr_inflight_hi_from_lost_packet(self, packet):
        size = packet.size
        inflight_prev = self.rs.tx_in_flight - size
        lost_prev = self.rs.lost - size
        lost_prefix = (self.BBRLossThresh * inflight_prev - lost_prev) / (
            1 - self.BBRLossThresh
        )
        inflight = inflight_prev + lost_prefix
        return inflight

    def bbr_handle_lost_packet(self, packet):
        if self.bw_probe_samples == 0:
            return
        self.rs.tx_in_flight = packet.tx_in_flight
        self.rs.lost = self.C.lost - packet.lost
        self.rs.is_app_limited = self.C.is_app_limited
        if self.bbr_is_inflight_too_high():
            self.rs.tx_in_flight = self.bbr_inflight_hi_from_lost_packet(packet)
            self.bbr_handle_inflight_too_high()

    def bbr_modulate_cwnd_for_recovery(self):
        if self.rs.newly_lost > 0:
            self.cwnd = max(self.cwnd - self.rs.newly_lost, self.mss)
        if self.packet_conservation:
            self.cwnd = max(self.cwnd, self.packet_in_flight)

    def consecutive_dupacks_received(self, packet=None):
        """Actions to be taken when three consecutive dupacks are received."""
        # fast retransmit in RFC 2001 and TCP Reno
        self.bbr_handle_lost_packet(packet)
        self.in_fast_recovery = True
        self.prior_cwnd = self.bbr_save_cwnd()
        self.cwnd = self.packet_in_flight + self.mss
        self.packet_conservation = True

    def more_dupacks_received(self, packet=None):
        """Actions to be taken when more than three consecutive dupacks are received."""
        # fast recovery
        self.in_fast_recovery = True
        self.bbr_modulate_cwnd_for_recovery()
        if self.round_start:
            self.packet_conservation = False

    def timer_expired(self, packet=None):
        """Actions to be taken when a timer expired."""
        # setting the congestion window to 1 segmenta
        self.bbr_handle_lost_packet(packet)
        self.prior_cwnd = self.bbr_save_cwnd()
        self.cwnd = self.packet_in_flight + self.mss

    def dupack_over(self):
        if not self.in_fast_recovery:
            return
        self.in_fast_recovery = False
        self.packet_conservation = False
        self.bbr_restore_cwnd()
