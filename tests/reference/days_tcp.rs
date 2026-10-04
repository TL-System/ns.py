//! Small explicit TCP flows observed from actual two-worker Days CPU execution.
use days_executor::{
    event_phase, run_cpu_with_observations, run_scalar_with_observations, validate,
    ArrivalDisposition, Backend, CpuConfig, Event, EventKey, EventKind, FlowDescriptor,
    FlowGeneratorKind, FlowGeneratorState, FlowId, GeneratorFeedbackState, GeneratorStatus,
    HostState, LinkDescriptor, LinkId, NodeDescriptor, NodeId, NodeKind, ObservationMode,
    PacketDescriptor, PacketKind, PayloadId, RemoteChannel, ScheduledEmission, SchedulerKind,
    SimulationImage, SwitchQueueState, SwitchState, TcpCongestionControl, TcpDataHeader,
    TcpGenerator, TcpReceiverState, TcpTransitionInput,
};
use std::collections::VecDeque;
const SOURCE: NodeId = NodeId(0);
const SINK: NodeId = NodeId(1);
const FORWARD: LinkId = LinkId(0);
const REVERSE: LinkId = LinkId(1);
const FLOW: FlowId = FlowId(0);
const FIRST: PayloadId = PayloadId(0);
const MSS: u64 = 512;
const ACK_BYTES: u64 = 40;
fn tcp_image(control: TcpCongestionControl, total_bytes: u64) -> SimulationImage {
    let first_size = MSS.min(total_bytes);
    let forward = LinkDescriptor {
        id: FORWARD,
        source: SOURCE,
        target: SINK,
        rate_bps: 8_000_000_000,
        propagation_ns: 100,
    };
    let reverse = LinkDescriptor {
        id: REVERSE,
        source: SINK,
        target: SOURCE,
        rate_bps: 8_000_000_000,
        propagation_ns: 100,
    };
    let first = PacketDescriptor {
        id: FIRST,
        flow: FLOW,
        size_bytes: first_size,
        ecn_marked: false,
        kind: PacketKind::TcpData(TcpDataHeader {
            sequence: 0,
            sent_time_ns: 0,
            retransmission: false,
        }),
    };
    SimulationImage {
        stop_time_ns: 4_000_000_000,
        nodes: vec![
            NodeDescriptor {
                id: SOURCE,
                kind: NodeKind::Host,
                state_slot: 0,
            },
            NodeDescriptor {
                id: SINK,
                kind: NodeKind::Host,
                state_slot: 1,
            },
        ],
        host_states: vec![
            HostState {
                egress_link: FORWARD,
                queue: VecDeque::new(),
                in_service: None,
                tx_ready_pending: false,
                generators: vec![FlowGeneratorState {
                    flow: FLOW,
                    packets_emitted: 0,
                    bytes_emitted: 0,
                    next_emission: ScheduledEmission {
                        status: GeneratorStatus::Scheduled,
                        departure_time_ns: 0,
                        payload: FIRST,
                    },
                    rng_state: 7,
                    feedback: GeneratorFeedbackState {
                        arrivals: 0,
                        outstanding_bytes: 0,
                        unacknowledged_bytes: 0,
                    },
                    kind: FlowGeneratorKind::Tcp(TcpGenerator::new(
                        total_bytes,
                        MSS,
                        ACK_BYTES,
                        control,
                    )),
                }],
                stages: Vec::new(),
                tcp_receivers: vec![],
                dcqcn_receivers: vec![],
                roce_receivers: None,
                pfc: None,
                next_origin_seq: 1,
                next_payload_seq: 1,
                sourced_packets: 0,
                departed_packets: 0,
                received_packets: 0,
            },
            HostState {
                egress_link: REVERSE,
                queue: VecDeque::new(),
                in_service: None,
                tx_ready_pending: false,
                generators: vec![],
                stages: Vec::new(),
                tcp_receivers: vec![TcpReceiverState::new(FLOW, ACK_BYTES)],
                dcqcn_receivers: vec![],
                roce_receivers: None,
                pfc: None,
                next_origin_seq: 0,
                next_payload_seq: 0,
                sourced_packets: 0,
                departed_packets: 0,
                received_packets: 0,
            },
        ],
        switch_states: vec![],
        flows: vec![FlowDescriptor {
            id: FLOW,
            source: SOURCE,
            target: SINK,
            priority: 0,
            feedback_priority: 0,
            route: vec![FORWARD],
            reverse_route: vec![REVERSE],
        }],
        initial_packets: vec![first],
        links: vec![forward, reverse],
        channels: vec![
            RemoteChannel::for_packet_link(forward, 1).unwrap(),
            RemoteChannel::for_packet_link(reverse, ACK_BYTES).unwrap(),
        ],
        initial_events: vec![Event {
            key: EventKey {
                time_ns: 0,
                phase: event_phase(EventKind::PacketArrival),
                origin_node: SOURCE,
                origin_seq: 0,
            },
            target: SOURCE,
            kind: EventKind::PacketArrival,
            payload: FIRST,
        }],
        seed: 1,
    }
}

fn state(control: TcpCongestionControl) -> String {
    format!(
        concat!(
            "{{\"cwnd_bytes\":{},\"ssthresh_bytes\":{},\"phase\":{},",
            "\"duplicate_acks\":{},\"recovery_high_sequence\":{},\"ca_credit\":{},",
            "\"cwnd_scaled\":{},\"ssthresh_scaled\":{},\"w_max_scaled\":{},",
            "\"w_last_max_scaled\":{},\"epoch_start_ns\":{},\"srtt_ns\":{},\"k_ns\":{}}}"
        ),
        control.cwnd_bytes(MSS),
        control.ssthresh_bytes(),
        control.phase() as u8,
        control.duplicate_acks(),
        control.recovery_high_sequence(),
        control.ca_credit(),
        control.cwnd_scaled(),
        control.ssthresh_scaled(),
        control.w_max_scaled(),
        control.w_last_max_scaled(),
        control
            .epoch_start_ns()
            .map_or("null".into(), |n| n.to_string()),
        control.srtt_ns(),
        control.cubic_k_ns()
    )
}

fn observe(name: &str, cubic: bool, avoidance: bool, loss: bool) -> String {
    let mut control = if cubic {
        TcpCongestionControl::cubic(MSS)
    } else {
        TcpCongestionControl::reno(MSS)
    };
    // Configure public initial controller state, never fabricate output transitions.
    if avoidance {
        match &mut control {
            TcpCongestionControl::Reno(s) => s.ssthresh_bytes = 4 * MSS,
            TcpCongestionControl::Cubic(s) => s.ssthresh_scaled = 4_000_000_000,
        }
    }
    if loss && !name.contains("timeout") {
        match &mut control {
            TcpCongestionControl::Reno(s) => s.cwnd_bytes = 8 * MSS,
            TcpCongestionControl::Cubic(s) => s.cwnd_scaled = 8_000_000_000,
        }
    }
    let total = if name.contains("timeout") {
        6 * MSS + 123
    } else if loss {
        20 * MSS + 123
    } else {
        12 * MSS + 123
    };
    let mut image = tcp_image(control, total);
    if loss {
        // A faster source overflows a four-packet waiting room at the bottleneck.
        // Drops are generated by CPU admission, not by controller calls.
        image.links[0].target = NodeId(2);
        image.links[0].rate_bps = 64_000_000_000;
        let bottleneck = LinkDescriptor {
            id: LinkId(2),
            source: NodeId(2),
            target: SINK,
            rate_bps: 8_000_000_000,
            propagation_ns: 100,
        };
        image.links.push(bottleneck);
        image.nodes.push(NodeDescriptor {
            id: NodeId(2),
            kind: NodeKind::Switch,
            state_slot: 0,
        });
        image.switch_states.push(SwitchState {
            physical_switch: 0,
            queues: vec![SwitchQueueState {
                egress_link: Some(LinkId(2)),
                scheduler: SchedulerKind::Fifo,
                queue_capacity_packets: if name.contains("timeout") { 1 } else { 4 },
                drop_mark: Default::default(),
                pfc: None,
                queue: Default::default(),
                in_service: None,
                tx_ready_pending: false,
            }],
            next_origin_seq: 0,
            arrived_packets: 0,
            dropped_packets: 0,
            departed_packets: 0,
        });
        image.flows[0].route.push(LinkId(2));
        image.channels[0] = RemoteChannel::for_packet_link(image.links[0], 1).unwrap();
        image
            .channels
            .push(RemoteChannel::for_packet_link(bottleneck, 1).unwrap());
    }
    validate(&image, Backend::Cpu { workers: 2 }).expect("valid CPU input");
    let cpu = run_cpu_with_observations(
        &image,
        None,
        CpuConfig {
            workers: 2,
            ..CpuConfig::default()
        },
        ObservationMode::Full,
    )
    .expect("actual CPU execution");
    let scalar = run_scalar_with_observations(&image, None, ObservationMode::Full)
        .expect("secondary Scalar check");
    assert_eq!(cpu.result, scalar);
    let result = cpu.result;
    let packets = result
        .observed_packets
        .iter()
        .map(|p| {
            let kind = match p.kind {
                PacketKind::TcpData(h) => format!(
                    "\"kind\":\"data\",\"sequence\":{},\"sent_ns\":{},\"retransmission\":{}",
                    h.sequence, h.sent_time_ns, h.retransmission
                ),
                PacketKind::TcpAck(h) => format!(
                    "\"kind\":\"ack\",\"acknowledgment\":{},\"echoed_sent_ns\":{}",
                    h.acknowledgment, h.echoed_sent_time_ns
                ),
                _ => panic!("unexpected packet"),
            };
            format!(
                "{{\"packet_id\":{},\"size_bytes\":{},{}}}",
                p.id.0, p.size_bytes, kind
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let departures = result
        .departures
        .iter()
        .map(|d| {
            format!(
                "{{\"packet_id\":{},\"time_ns\":{}}}",
                d.payload.0, d.time_ns
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let arrivals = result
        .arrivals
        .iter()
        .map(|a| {
            let disposition = match a.disposition {
                ArrivalDisposition::Admitted => "admitted",
                ArrivalDisposition::Dropped => "dropped",
                ArrivalDisposition::Delivered => "delivered",
                ArrivalDisposition::Feedback => "feedback",
            };
            format!(
                "{{\"packet_id\":{},\"time_ns\":{},\"disposition\":\"{}\"}}",
                a.payload.0, a.time_ns, disposition
            )
        })
        .collect::<Vec<_>>()
        .join(",");
    let transitions = result.diagnostics.as_ref().unwrap().tcp_transitions.iter().map(|t| {
        let input = match t.input {
            TcpTransitionInput::NewAck { acknowledged_bytes, rtt_sample_ns, flight_size_bytes, acknowledgment } =>
                format!("{{\"kind\":\"new_ack\",\"acknowledged_bytes\":{},\"rtt_sample_ns\":{},\"flight_size_bytes\":{},\"acknowledgment\":{}}}",
                    acknowledged_bytes, rtt_sample_ns, flight_size_bytes, acknowledgment),
            TcpTransitionInput::DuplicateAck { flight_size_bytes, recovery_high_sequence } =>
                format!("{{\"kind\":\"duplicate_ack\",\"flight_size_bytes\":{},\"recovery_high_sequence\":{}}}", flight_size_bytes, recovery_high_sequence),
            TcpTransitionInput::Timeout { flight_size_bytes } =>
                format!("{{\"kind\":\"timeout\",\"flight_size_bytes\":{}}}", flight_size_bytes),
        };
        format!("{{\"time_ns\":{},\"node_id\":{},\"flow_id\":{},\"input\":{},\"before\":{},\"after\":{}}}",
            t.key.time_ns, t.node.0, t.flow.0, input, state(t.before), state(t.after))
    }).collect::<Vec<_>>().join(",");
    let FlowGeneratorKind::Tcp(final_tcp) = result.host_states[0].generators[0].kind else {
        panic!()
    };
    format!(concat!("{{\"name\":\"{}\",\"input\":{{\"controller\":\"{}\",\"mss_bytes\":{},",
        "\"ack_bytes\":{},\"total_bytes\":{},\"initial_control\":{},\"rate_bps\":8000000000,",
        "\"propagation_ns\":100,\"initial_rto_ns\":1000000000,",
        "\"min_rto_ns\":1000000000,\"max_rto_ns\":60000000000,\"rto_granularity_ns\":1000000,",
        "\"stop_time_ns\":4000000000,",
        "\"bottleneck_loss\":{},\"source_rate_bps\":{},\"waiting_capacity_packets\":{},\"seed\":1}},",
        "\"output\":{{\"packets\":[{}],\"departures\":[{}],\"arrivals\":[{}],\"transitions\":[{}],",
        "\"highest_ack\":{},\"bytes_in_flight\":{},\"received_data_packets\":{},\"received_data_bytes\":{},",
        "\"feedback_packets\":{},\"dropped_packets\":{},\"pending_events\":{},\"resident_packets\":{}}}}}"),
        name, if cubic { "cubic" } else { "reno" }, MSS, ACK_BYTES, total, state(control),
        loss, if loss {64_000_000_000u64} else {8_000_000_000u64}, if loss {4} else {0},
        packets, departures, arrivals, transitions, final_tcp.highest_ack, final_tcp.bytes_in_flight,
        result.summary.received_packets, result.summary.received_bytes, result.summary.feedback_packets,
        result.summary.dropped_packets, result.pending_events.len(), result.resident_packets.len())
}

fn main() {
    let cases = [
        observe("reno_growth_short_tail", false, false, false),
        observe("reno_avoidance", false, true, false),
        observe("cubic_growth_short_tail", true, false, false),
        observe("cubic_avoidance", true, true, false),
        observe("reno_bottleneck_loss", false, false, true),
        observe("reno_bottleneck_timeout", false, false, true),
        observe("cubic_bottleneck_loss", true, false, true),
    ];
    println!(concat!("{{\"reference\":{{\"revision\":\"9ff20eac16dcdf752510b05cbcf526684dc05146\",",
        "\"backend\":\"cpu\",\"workers\":2,\"observation_mode\":\"full\",\"scalar_equal\":true}},\"cases\":[{}]}}"), cases.join(","));
}
