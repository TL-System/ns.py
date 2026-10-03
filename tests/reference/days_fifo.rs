//! Regenerate one FIFO fixture through the public current Days CPU API.
//!
//! Arrivals are preloaded at the switch, so the source link is route metadata:
//! only the switch egress serializes these packets. No stochastic input is used.

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
const STOP_NS: u64 = 5225;
const WORKERS: usize = 2;
// (identity, size in bytes, switch arrival in ns). One byte takes exactly 1 ns.
const PACKETS: &[(u64, u64, u64)] = &[
    (0, 1000, 0),
    (3, 500, 0),
    (6, 250, 500),
    (9, 750, 1750),
    (12, 125, 5000),
];

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

fn image() -> SimulationImage {
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
        stop_time_ns: STOP_NS,
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
        host_states: vec![host(LinkId(0), PACKETS.len() as u64), host(LinkId(2), 0)],
        switch_states: vec![SwitchState {
            physical_switch: 0,
            queues: vec![SwitchQueueState {
                egress_link: Some(LinkId(1)),
                scheduler: SchedulerKind::Fifo,
                queue_capacity_packets: 0, // Days: zero means unbounded waiting room.
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
        flows: vec![FlowDescriptor {
            id: FlowId(0),
            source: NodeId(0),
            target: NodeId(2),
            priority: 0,
            feedback_priority: 0,
            route: vec![LinkId(0), LinkId(1)],
            reverse_route: vec![],
        }],
        initial_packets: PACKETS
            .iter()
            .map(|&(id, size_bytes, _)| PacketDescriptor {
                id: PayloadId(id),
                flow: FlowId(0),
                size_bytes,
                ecn_marked: false,
                kind: PacketKind::Data,
            })
            .collect(),
        links: vec![
            source_link,
            switch_link,
            // The terminal host's unused egress still needs a valid link descriptor.
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
        initial_events: PACKETS
            .iter()
            .enumerate()
            .map(|(sequence, &(id, _, time_ns))| Event {
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

fn main() {
    let image = image();
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
    // Secondary check only; the emitted observations come from cpu.result.
    let scalar = run_scalar_with_observations(&image, None, ObservationMode::Full)
        .expect("scalar cross-check");
    assert_eq!(cpu.result, scalar);
    let result = cpu.result;
    assert!(result.pending_events.is_empty());
    assert!(result.resident_packets.is_empty());

    let input = PACKETS
        .iter()
        .map(|&(id, size, time)| {
            format!("{{\"packet_id\":{id},\"size_bytes\":{size},\"arrival_ns\":{time}}}")
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
    println!(
        concat!(
            "{{\"reference\":{{\"revision\":\"{}\",\"backend\":\"cpu\",",
            "\"workers\":{},\"observation_mode\":\"full\",\"scalar_equal\":true}},",
            "\"input\":{{\"rate_bps\":{},\"propagation_ns\":{},\"stop_time_ns\":{},",
            "\"queue_capacity_packets\":0,\"flow_id\":0,\"priority\":0,",
            "\"route\":[0,1],\"arrival_node\":1,\"seed\":18,\"packets\":[{}]}},",
            "\"output\":{{\"departures\":[{}],\"arrivals\":[{}],",
            "\"summary\":{{\"admitted_packets\":{},\"admitted_bytes\":{},",
            "\"departed_packets\":{},\"departed_bytes\":{},",
            "\"received_packets\":{},\"received_bytes\":{},",
            "\"dropped_packets\":{},\"dropped_bytes\":{}}},",
            "\"pending_events\":0,\"resident_packets\":0}}}}"
        ),
        REVISION,
        WORKERS,
        RATE_BPS,
        PROPAGATION_NS,
        STOP_NS,
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
    );
}
