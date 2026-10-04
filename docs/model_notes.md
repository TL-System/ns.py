# Model notes for network experiments

ns.py teaches network behavior through small SimPy components. A source calls
`out.put(packet)`; a port or scheduler waits for work and serialization; a wire
adds propagation; a sink records arrivals. These are algorithm models with
explicit boundaries, rather than full operating-system network stacks.

The [component inventory](modernization.md#component-inventory) records tests
and reference evidence. Cross-simulator claims refer to pinned Days CPU revision
`9ff20eac16dcdf752510b05cbcf526684dc05146`, not its historical implementations.
Ordinary pytest runs consume recorded CPU fixtures without Rust or Days.
[Reference instructions](../tests/reference/README.md) describe regeneration.

## Time, size, and observation

| Quantity | Unit or meaning |
| --- | --- |
| Simulation clocks, arrival distributions, RTT/RTO | Seconds; ordinary SimPy uses floating-point time. |
| `Packet.size`, buffer byte limits, token capacities | Bytes; generic packets may have fractional size for analytical queue models. Payload is opaque and does not determine serialization size. |
| Port/scheduler/shaper link rates | Bits/second; service takes `8 * packet.size / rate`. Port rate zero means unlimited service; scheduler service assumes a positive rate. |
| BBR delivery and pacing rate | Bytes/second; new-data pacing takes `segment_bytes / pacing_rate`. |
| `StackDelayer.speed` | Bytes/second. |
| TCP sequence, window, flight, and application volume | Whole bytes at the transport boundary; controller windows can retain fractional credit. |
| `PacketSink.waits` | `env.now - packet.time`: end-to-end delay including service and propagation, not just queue waiting. TCP retries retain the first-transmit time. |

`Port.qlimit` includes waiting packets, local service, and objects retained for a
zero-buffer downstream component. An exact fit is accepted; `None` is unlimited;
zero admits nothing. `PortMonitor` includes retention until release, optionally
subtracting local service. Scheduler `size()`/`byte_size()` describe only work
waiting for that scheduler's local service. `ServerMonitor` optionally adds its
current packet by mapped class, and excludes downstream retention. A retained
object is therefore physical ownership, not necessarily eligible local work.
`SimplePacketSwitch` and `FairPacketSwitch` use the same resident-capacity rule.

Numeric `env.run(until=t)` stops before ordinary events at `t`. Finite simulations
can drain with `env.run()` if no monitor or source runs forever; otherwise use an
explicit observation boundary and inspect outstanding work. Samples at an exact
completion timestamp can reflect whichever event SimPy processes first.

Days uses integer nanoseconds and rounds every serialization interval upward;
ns.py keeps floating-point intervals. Integral-nanosecond fixtures permit close
comparison. For fractional intervals, the rounding bound grows with the number
of causal service steps. Floating-point tag rounding can also change near ties.
A tolerance cannot justify a different packet selection or retransmission.

Days orders equal-time arrivals before completions/timeouts and service
selection. SimPy orders by time, priority, then insertion. Local zero-time
scheduler waits include already scheduled arrivals before selection, but cannot
replicate global phases for arbitrary chains of user events. At an ACK/timeout
tie an ACK first cancels recovery; a timeout first may emit an extra attempt.
See the [TCP timing contract](tcp_timing.md) for the tested boundary behavior.

## Scheduling choices

All four schedulers serialize nonpreemptively: an arriving high-ranked packet
cannot interrupt service already in progress. A `flow_classes` mapping combines
flows into scheduling classes while preserving their routing flow IDs.

- **SP:** larger priority values win; classes with equal priority share FIFO
  order. Persistent high-priority backlog can starve lower priorities.
- **DRR:** textbook active-list order, a fixed quantum per class visit, and byte
  deficit carry while a class remains backlogged. Quanta are
  `max(1500, mtu_bytes) * weight / min_weight`. Oversized heads accumulate credit
  across visits; they do not enlarge all classes' quanta. An empty waiting class
  discards credit immediately. Days instead scans a numerical class cursor,
  credits classes at cursor wraps, and can retain empty-class credit until a
  wrap. The [DRR counterexamples](../evidence/phase3_reference.md) preserve these
  deliberate order and credit differences.
- **WFQ:** the selected Days packet-active recurrence, approximating fluid GPS.
  A class is active while it has queued or locally in-service physical packets.
  With rate `R` in bits/second and packet length `L` bytes, its finish tag is
  `max(V, previous_finish[class]) + 8*L/R/weight[class]`; elapsed virtual time
  advances by `elapsed / sum(active_weights)`. Completion retires its weight
  after advancing the clock; an idle server resets virtual and finish history.
  The smallest finish tag wins, with admission order for exact ties. Fluid GPS
  can choose a different next packet: the five-class counterexample in
  [WFQ evidence](../evidence/phase3_wfq.md) establishes the chosen recurrence.
  Days rate-scales these tags and uses exact rational arithmetic.
- **Virtual Clock:** tag an arrival with
  `max(now, previous_tag[class]) + 8*L*vtick[class]`, where `vtick` is seconds per
  bit. Tags rank packets without holding an otherwise idle link until tag time.
  The model implements the paper's forwarding rule, omitting flow-monitoring
  feedback, periodic synchronization, and overflow policy. Current Days CPU has
  no counterpart; [independent evidence](../evidence/phase3_virtual_clock.md)
  uses the algorithm reference and calculated timings.

To compose one bounded buffer with several scheduling stages, configure the
upstream owner with `zero_downstream_buffer=True` and its consumer with
`zero_buffer=True`. The upstream retains each original packet until the final
consumer releases it through the existing callback chain. Reordered completion
must remove that exact object, rather than the first object in an upstream FIFO.
The small internal `utils/retained_store.py` helper centralizes this operation.
[Composition evidence](../evidence/phase3_composition.md) covers FIFO and tagged
ownership stores, reentrant callbacks, and mapped-class telemetry.

## Congestion control and transport

TCP sends a byte stream with cumulative ACKs and NewReno-style recovery. Short
last segments exhaust the exact byte budget. Outstanding bytes count unique
ranges, and retransmissions emit fresh packet attempts without double-counting
flight. Each connection has one oldest-range timer; partial recovery ACKs can
retransmit the next hole. Receivers merge overlapping ranges and acknowledge
only the contiguous prefix. `TCPSink.bytes_delivered` counts unique application
bytes; inherited sink statistics count physical arrivals, including duplicates.

Each `TCPSink` represents one connection starting at sequence zero. It emits an
immediate 40-byte ACK with flow ID `data_flow_id + 10000`; route generation
rejects data/ACK ID collisions. These models omit handshakes, TCP timestamps,
SACK, receiver-window limits, and delayed ACKs. New transmission stops at the
exclusive application finish time, while already sent data can recover and drain.
Karn sampling is conservative: ambiguous or retransmitted ranges supply no RTT.
Days can learn from echoed attempt timestamps in some of those cases.

Reno uses newly ACKed byte credit and actual flight at loss. CUBIC follows the
pinned Days equations with floating-point curves and a retained loss fraction
`beta=0.7`; an explicit beta argument now means the fraction retained. The
models do not claim complete Linux or RFC conformance. Actual CPU fixtures cover
aligned Reno/CUBIC scenarios and preserve the documented Karn/SRTT divergence;
see [controller/reference evidence](../evidence/phase5.md).

[BBR](bbr.md) is an educational bandwidth/propagation-delay controller: BBRv1
core estimation with a deterministic four-phase ProbeBW teaching cycle. It is
not Linux BBRv3. Application-limited filtering, packet-timed rounds, paced new
data, ProbeRTT, and byte-conserving recovery have independent tests and composed
flows. Current Days CPU has no BBR counterpart. The separate model document
lists its gains, sampling rules, probe timing, and omitted production mechanisms.

## RED, shaping, sources, and real traffic

RED updates a pre-arrival occupancy EWMA on every arrival, including capacity
drops. It drops unconditionally at/above the maximum threshold and draws
independently between thresholds. There is no count correction, ECN marking, or
continuous idle decay. Days uses deterministic counter signaling and waiting
occupancy; Python uses random draws and Port resident occupancy. Aligning seeds
or numeric queue limits cannot establish equal drops. See
[RED evidence](../evidence/phase6_queues_shapers.md) for explicit draws and limits.

Token buckets begin full, refill byte credit at `rate_bps / 8`, and cap idle
credit. Single-rate tokens gate departures unless optional peak serialization
is enabled, when they gate serialization starts. Completed-packet windows can
then bunch and require a packetization allowance. Oversized packets wait for
the deficit and leave zero credit, relaxing the ordinary burst envelope for
that packet. Two-rate shaper colors describe head eligibility before a wait.
With PIR configured, only green consumes committed credit; yellow/red preserve
it. Without PIR, CIR gates all traffic: green consumes available committed
tokens, while yellow waits for its deficit and consumes the resulting credit,
leaving the committed bucket empty. These colors differ from arrival metering:
color-blind `TrTCM` colors immediately, preserves flow ID, and neither waits nor
drops. The [shaper evidence](../evidence/phase6_queues_shapers.md) states envelopes
and color rules precisely.

Distribution sources emit first at their initial delay; subsequent intervals
are finite and nonnegative, and zero permits same-time bursts. A finite byte
budget shortens the final packet exactly. Trace times are source-relative,
nondecreasing, and retain file order on ties. Both use exclusive finish times.
An unbounded callable source must eventually advance time and bytes as needed.
Flow streaming helpers retain future arrivals across polls. MAP/BMAP helpers
validate balanced transition tables and use stationary-time initialization;
Pareto on/off helpers use seconds and a bit-budget endpoint for packet bursts.
These changes and the source/iterator first-arrival distinction are detailed in
[source evidence](../evidence/phase6_sources.md).

Socket proxies count actual payload bytes, keep distinct TCP connections/UDP
clients, and preserve whole UDP datagrams. They use positive cooperative polls
and monotonic wall deadlines within plain SimPy. EOF closes an entire TCP flow;
late simulated packets cannot reopen its ID. Explicit `close()` releases owned
sockets and queued sends. They omit half-close and simulated TCP loss repair,
and have no current CPU counterpart. [Proxy notes](proxies.md) explain setup,
timeouts, polling latency, statistics, and resource lifetime.

For a finite teaching experiment, run
`uv run --locked python examples/composed_network.py`. Change one rate,
capacity, or class map at a time and compare packet order, exact delivered bytes,
and queue drain before interpreting aggregate throughput.
