# Educational BBR model

`ns.flow.bbr.BBR` is a small model of BBR's bandwidth/propagation-delay control.
It is **not Linux BBRv3**. Existing `test_bbrv3` filenames are retained for test
history, but do not imply v3 conformance. The former RFC 8899 attribution was
incorrect: that RFC describes Datagram Packetization Layer Path MTU Discovery.

The core reference is [Linux v6.12's BBR controller](https://github.com/torvalds/linux/blob/v6.12/net/ipv4/tcp_bbr.c):
its packet-timed bandwidth filter, full-pipe detection, Startup/Drain modes, and
ProbeRTT explain the mechanisms preserved here. The [BBR congestion-control
draft, revision 02](https://datatracker.ietf.org/doc/html/draft-cardwell-iccrg-bbr-congestion-control-02)
describes BBRv2 and its richer path model; naming similar probe phases does not
implement that model. Delivery sampling follows the [delivery-rate draft,
revision 02](https://datatracker.ietf.org/doc/html/draft-cheng-iccrg-delivery-rate-estimation-02)
and [Linux v6.12's TCP rate sampler](https://github.com/torvalds/linux/blob/v6.12/net/ipv4/tcp_rate.c).

## Delivery measurements

The sender counts newly acknowledged **unique bytes**, including partial segment
prefixes, once. `Connection.delivered` therefore equals the cumulative application
ACK frontier. Each physical attempt snapshots delivered bytes, delivery/send
clocks, application-limited status, and loss totals. Retransmissions refresh these
snapshots with their latest attempt time. `Packet.time` still holds the original
first transmission time for sink latency; `Packet.sent_time` supplies the attempt
clock. Queued attempts retain their metadata when logical state changes.

Every valid incoming ACK begins a fresh sample group. An advancing ACK credits
all newly covered ranges and selects the snapshot with greatest prior delivered
count, breaking ties by latest attempt time. Sample bytes are total delivery
since that snapshot; its interval is the larger of send elapsed and ACK elapsed.
The quotient is bytes/second. This send interval prevents ACK compression from
claiming a rate higher than the corresponding transmission interval permits.
Zero intervals and intervals shorter than the known minimum RTT produce no rate;
they still deliver bytes. Duplicate ACKs reset feedback but never credit delivery.
Loss feedback records newly declared lost bytes since the last finalized group.
It describes sender loss declarations, including repeat timeouts, rather than
counting unique application bytes permanently missing.

An application-limited marker is a delivered-byte frontier, retained until total
delivery **passes** that frontier. The sender marks insufficient full-segment
supply when neither window exhaustion nor recovery estimates explain it. A
finite tail can be application-limited; an unlimited bulk source cannot, even
though the sender stages it one MSS at a time. Lower application-limited samples
cannot replace or age out a bandwidth estimate; a higher sample can discover
capacity. An intentionally reduced ProbeRTT flight is also marked limited.

## Controller behavior

- A packet-timed round starts when an ACKed attempt's prior delivered count
  reaches the saved delivered frontier. A fresh ACK group must contain delivery
  metadata; an absent snapshot cannot begin a round. The bandwidth filter stores
  one maximum per round over ten rounds, irrespective of ACK density. Old values
  expire when the next accepted sample advances the filter's round window.
- Startup paces with gain 2.885 and grows cwnd by actual acknowledged bytes.
  Pacing does not decrease during Startup. Once per round, a valid, unrestricted
  rate observation checks whether the filtered maximum grew by at least 25%.
  Three rounds without that growth mark the pipe full. Application-limited and
  unusable rate samples cannot terminate Startup. Drain uses gain `1 / 2.885`
  until actual remaining flight reaches one estimated BDP.
- ProbeBW uses a deterministic four-phase teaching cycle: DOWN at pacing gain
  0.9, CRUISE at 1, REFILL at 1, and UP at 1.1. DOWN waits for flight to drain to
  one BDP; CRUISE and REFILL each advance on a packet-timed round. UP requires
  a round and at least a minimum RTT, or terminates early when an ACK reports
  newly declared loss. This is neither Linux v1's eight-gain cycle nor the
  randomized, loss-bounded probing of v2/v3.
- The model estimates BDP as bandwidth in bytes/second times minimum RTT in
  seconds. Cwnd targets twice that BDP after filling the pipe, with a minimum
  of four MSS. Before a bandwidth observation, pacing uses initial cwnd/RTT.
  Before an RTT observation, BDP uses the positive initial RTT estimate.
- The minimum RTT expires ten seconds after its last improvement or replacement.
  Expiry is determined before accepting a new minimum. ProbeRTT caps cwnd at
  four MSS, waits for actual flight to drain to that level, then holds for at
  least 200 ms and one packet-timed round. Exit restores saved cwnd and refreshes
  expiry. An eligible zero RTT is valid; absence of a Karn-eligible RTT is not
  encoded as zero in the model.
- Timeout and fast loss enter byte conservation with the actual outstanding
  flight, bounded below by four MSS. Each subsequent advancing ACK allows
  `remaining_flight + newly_acked` bytes of window. Ordinary duplicates create
  no credit. Conservation persists until cumulative delivery covers the entry
  flight, or the transport explicitly exits its fast-recovery frontier. Saved
  cwnd is restored on exit; the filled-pipe BDP cap then applies. When recovery
  and ProbeRTT overlap, each entry preserves the other mode's saved window,
  so a temporary cap cannot erase the credit restored after both finish. Repeated
  timeout retains the saved window and advances the delivery frontier.

## Deliberate omissions

There is no v2/v3 `bw_hi`/`bw_lo`, `inflight_hi`/`inflight_lo`, ECN model, loss-rate
threshold, randomized probe scheduling, ACK-aggregation allowance, policer model,
TSO/GSO budget, pacing margin, idle-restart suppression of ProbeRTT, or packet
quantization matching Linux. Loss recovery conserves bytes; it does not install
an enduring multiplicative bandwidth or inflight cap. Four-phase gains retain
the earlier public teaching model, with corrected timing and measurements.
Floating-point seconds and whole-byte transport segmentation remain ns.py's
units. A fractional window can produce short segments; there is no Linux packet
window quantization. Controller RTT uses the conservative sender Karn eligibility,
so it can learn less often than a timestamp/SACK-capable transport.

The [TCP timing contract](tcp_timing.md) defines segmentation, one oldest-range
RTO, deadline behavior, recovery retransmission ownership, and synchronous ACKs.
Retransmissions remain immediate recovery actions. New data is paced at
`segment_bytes / pacing_rate`; link ports separately convert bytes to bits.
The current Days CPU revision has no BBR implementation, so BBR acceptance uses
independent rate/round/probe observations and real SimPy flows, not a CPU parity
claim. Tests cover a 100000-byte/s bottleneck, sparse writes, exact delivery after
fast loss, synchronous zero-time ACKs, and probe/recovery boundaries.
