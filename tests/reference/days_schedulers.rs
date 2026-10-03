//! Replay five small scheduler cases through the public current Days CPU API.
//!
//! Arrivals are explicit switch inputs; the source hop is route metadata only.
//! The DRR activation-order and WFQ clock cases deliberately record differences.

use days_executor::{
    event_phase, run_cpu_with_observations, run_scalar_with_observations, validate,
    ArrivalDisposition, Backend, CpuConfig, Event, EventKey, EventKind, FlowDescriptor, FlowId,
    HostState, LinkDescriptor, LinkId, NodeDescriptor, NodeId, NodeKind, ObservationMode,
    PacketDescriptor, PacketKind, PayloadId, RemoteChannel, SchedulerKind, SimulationImage,
    SwitchQueueState, SwitchState,
};

const REVISION: &str = "9ff20eac16dcdf752510b05cbcf526684dc05146";
const RATE_BPS: u64 = 8_000_000_000;
const PROPAGATION_NS: u64 = 100;
const WORKERS: usize = 2;
// (identity, class/flow, size in bytes, switch arrival in ns).
// At 8 Gbit/s, converting bytes to bits gives exactly 1 ns per byte.
type PacketInput = (u64, u64, u64, u64);

fn host(egress_link: LinkId, next_origin_seq: u64) -> HostState {
    HostState {
        egress_link,
        queue: Default::default(),
        in_service: None,
        tx_ready_pending: false,
        generators: vec![],
        stages: vec![],
        tcp_receivers: vec![],
        dcqcn_receivers: vec![],
        roce_receivers: None,
        pfc: None,
        next_origin_seq,
        next_payload_seq: 0,
        sourced_packets: 0,
        departed_packets: 0,
        received_packets: 0,
    }
}

fn image(
    scheduler: SchedulerKind,
    class_count: u64,
    packets: &[PacketInput],
    stop_ns: u64,
) -> SimulationImage {
    let source_link = LinkDescriptor {
        id: LinkId(0),
        source: NodeId(0),
        target: NodeId(1),
        rate_bps: RATE_BPS,
        propagation_ns: 0,
    };
    let switch_link = LinkDescriptor {
        id: LinkId(1),
        source: NodeId(1),
        target: NodeId(2),
        rate_bps: RATE_BPS,
        propagation_ns: PROPAGATION_NS,
    };
    SimulationImage {
        stop_time_ns: stop_ns,
        nodes: vec![
            NodeDescriptor {
                id: NodeId(0),
                kind: NodeKind::Host,
                state_slot: 0,
            },
            NodeDescriptor {
                id: NodeId(1),
                kind: NodeKind::Switch,
                state_slot: 0,
            },
            NodeDescriptor {
                id: NodeId(2),
                kind: NodeKind::Host,
                state_slot: 1,
            },
        ],
        host_states: vec![host(LinkId(0), packets.len() as u64), host(LinkId(2), 0)],
        switch_states: vec![SwitchState {
            physical_switch: 0,
            queues: vec![SwitchQueueState {
                egress_link: Some(LinkId(1)),
                scheduler,
                queue_capacity_packets: 0, // Days: unbounded waiting room.
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
        }],
        flows: (0..class_count)
            .map(|class| FlowDescriptor {
                id: FlowId(class),
                source: NodeId(0),
                target: NodeId(2),
                priority: 0,
                feedback_priority: 0,
                route: vec![LinkId(0), LinkId(1)],
                reverse_route: vec![],
            })
            .collect(),
        initial_packets: packets
            .iter()
            .map(|&(id, class, size_bytes, _)| PacketDescriptor {
                id: PayloadId(id),
                flow: FlowId(class),
                size_bytes,
                ecn_marked: false,
                kind: PacketKind::Data,
            })
            .collect(),
        links: vec![
            source_link,
            switch_link,
            // The terminal host's unused egress needs a valid descriptor.
            LinkDescriptor {
                id: LinkId(2),
                source: NodeId(2),
                target: NodeId(1),
                rate_bps: RATE_BPS,
                propagation_ns: 0,
            },
        ],
        channels: vec![
            RemoteChannel::for_packet_link(source_link, 1).unwrap(),
            RemoteChannel::for_packet_link(switch_link, 1).unwrap(),
        ],
        initial_events: packets
            .iter()
            .enumerate()
            .map(|(sequence, &(id, _, _, time_ns))| Event {
                key: EventKey {
                    time_ns,
                    phase: event_phase(EventKind::RemoteArrival),
                    origin_node: NodeId(0),
                    origin_seq: sequence as u64,
                },
                target: NodeId(1),
                kind: EventKind::RemoteArrival,
                payload: PayloadId(id),
            })
            .collect(),
        seed: 18,
    }
}

fn observe(
    name: &str,
    scheduler: SchedulerKind,
    scheduler_json: &str,
    class_count: u64,
    packets: &[PacketInput],
    stop_ns: u64,
) -> String {
    let image = image(scheduler, class_count, packets, stop_ns);
    validate(&image, Backend::Cpu { workers: WORKERS }).expect("valid CPU input");
    let cpu = run_cpu_with_observations(
        &image,
        None,
        CpuConfig {
            workers: WORKERS,
            ..CpuConfig::default()
        },
        ObservationMode::Full,
    )
    .expect("actual CPU execution");
    // The CPU result supplies the JSON. Scalar is only a secondary cross-check.
    let scalar = run_scalar_with_observations(&image, None, ObservationMode::Full)
        .expect("scalar cross-check");
    assert_eq!(cpu.result, scalar);
    let result = cpu.result;
    assert!(result.pending_events.is_empty());
    assert!(result.resident_packets.is_empty());

    let input = packets
        .iter()
        .map(|&(id, class, size, time)| {
            format!(
                concat!(
                    "{{\"packet_id\":{},\"class_id\":{},\"flow_id\":{},",
                    "\"size_bytes\":{},\"arrival_ns\":{}}}"
                ),
                id, class, class, size, time
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
    format!(
        concat!(
            "{{\"name\":\"{}\",\"input\":{{\"scheduler\":{},",
            "\"rate_bps\":{},\"propagation_ns\":{},\"stop_time_ns\":{},",
            "\"queue_capacity_packets\":0,\"class_mapping\":\"flow_id\",",
            "\"route\":[0,1],\"arrival_node\":1,\"seed\":18,\"packets\":[{}]}},",
            "\"output\":{{\"departures\":[{}],\"arrivals\":[{}],",
            "\"summary\":{{\"admitted_packets\":{},\"admitted_bytes\":{},",
            "\"departed_packets\":{},\"departed_bytes\":{},",
            "\"received_packets\":{},\"received_bytes\":{},",
            "\"dropped_packets\":{},\"dropped_bytes\":{}}},",
            "\"pending_events\":0,\"resident_packets\":0}}}}"
        ),
        name,
        scheduler_json,
        RATE_BPS,
        PROPAGATION_NS,
        stop_ns,
        input,
        departures,
        arrivals,
        result.summary.admitted_packets,
        result.summary.admitted_bytes,
        result.summary.departed_packets,
        result.summary.departed_bytes,
        result.summary.received_packets,
        result.summary.received_bytes,
        result.summary.dropped_packets,
        result.summary.dropped_bytes,
    )
}

fn main() {
    let cases = [
        observe(
            "sp_boundaries_ties_idle",
            SchedulerKind::static_priority(vec![1, 9, 9]),
            "{\"kind\":\"sp\",\"priorities\":[1,9,9]}",
            3,
            &[
                (0, 0, 1000, 0),
                (3, 1, 250, 0),
                (6, 0, 500, 100),
                (9, 2, 125, 250),
                (12, 1, 125, 250),
                (15, 1, 125, 750),
                (18, 0, 125, 5000),
            ],
            5225,
        ),
        observe(
            "drr_credit_carry_idle",
            SchedulerKind::deficit_round_robin(vec![1500, 3000]),
            "{\"kind\":\"drr\",\"weights\":[1,2],\"quanta_bytes\":[1500,3000]}",
            2,
            &[
                (0, 0, 4000, 0),
                (3, 1, 1000, 0),
                (6, 1, 2500, 0),
                (9, 0, 1000, 0),
                (12, 1, 500, 0),
                (15, 0, 2000, 15000),
            ],
            17100,
        ),
        observe(
            "drr_activation_order_difference",
            SchedulerKind::deficit_round_robin(vec![1500, 1500]),
            "{\"kind\":\"drr\",\"weights\":[1,1],\"quanta_bytes\":[1500,1500]}",
            2,
            &[(0, 1, 1000, 0), (3, 0, 1000, 0)],
            2100,
        ),
        observe(
            "wfq_tags_ties_idle",
            SchedulerKind::weighted_fair_queue(vec![1, 2]),
            "{\"kind\":\"wfq\",\"weights\":[1,2]}",
            2,
            &[
                (0, 0, 1000, 0),
                (3, 1, 500, 0),
                (6, 1, 1500, 0),
                (9, 0, 1000, 5000),
            ],
            6100,
        ),
        observe(
            "wfq_active_clock_difference",
            SchedulerKind::weighted_fair_queue(vec![1, 1, 1, 1, 1]),
            "{\"kind\":\"wfq\",\"weights\":[1,1,1,1,1]}",
            5,
            &[
                (0, 0, 10, 0),
                (3, 1, 100, 0),
                (6, 2, 13, 0),
                (9, 3, 14, 0),
                (12, 4, 10, 15),
            ],
            247,
        ),
    ];
    println!(
        concat!(
            "{{\"reference\":{{\"revision\":\"{}\",\"backend\":\"cpu\",",
            "\"workers\":{},\"observation_mode\":\"full\",\"scalar_equal\":true}},",
            "\"cases\":[{}]}}"
        ),
        REVISION,
        WORKERS,
        cases.join(","),
    );
}
