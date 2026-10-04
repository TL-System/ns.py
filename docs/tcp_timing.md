# TCP Timing Contract

Both `TCPPacketGenerator` and `BBRPacketGenerator` send a byte stream through
`put()`/`out` connections. Each `TCPSink` represents one connection whose first
data byte has sequence zero. These transport models omit connection handshakes,
TCP timestamps, SACK, receive-window limits, and delayed ACKs.

Sequences, data sizes, congestion windows, and in-flight counts are bytes. TCP
segments contain whole bytes and follow the controller's positive integer `mss`
(512 if omitted). A finite flow's final segment contains exactly the remaining
bytes. Fractional congestion-window credit allows only its whole-byte prefix.
Generic packet/link sizes can still be floats; TCP's byte-stream rules are stricter.

## Receiver and delivery accounting

`TCPSink.recv_buffer` stores sorted, merged half-open byte intervals `[start,end)`.
Adjacent ranges merge, overlaps contribute no second copy, and a gap prevents
the cumulative ACK frontier `next_seq_expected` (`RCV.NXT`) from advancing.
The merged `[0, RCV.NXT)` prefix remains in the buffer to absorb late duplicates;
this is a received-range ledger rather than application payload storage.

`TCPSink.bytes_delivered` is a read-only view of `RCV.NXT`: the number of unique
contiguous application bytes. Buffered data beyond a gap waits for the gap to
close. Inherited `packets_received`, `bytes_received`, `arrivals`, and `waits`
describe **physical arrivals**, including repeated data after loss of an ACK.
For example, receiving a 123-byte segment twice counts 246 physical bytes but
delivers 123 application bytes. Delivery counting is independent of optional
arrival/wait sample recording.

Every physical data arrival generates an immediate 40-byte cumulative ACK,
including duplicate and out-of-order data. ACK flow IDs equal the data flow ID
plus 10000. Both senders accept only their own flow's ACKs within the transmitted
byte range; stale, unrelated, noninteger, and future ACKs cannot release credit.
The receiver echoes BBR's delivery-rate fields without owning RTT/RTO estimation.

## Sender state and packet ownership

Each sender keeps logical outstanding segment state keyed by the segment's
starting byte sequence. Every new send or retransmission emits a fresh `Packet`.
Queued physical attempts remain unchanged when an ACK retires or trims logical
state. A partial ACK leaves just the unacknowledged suffix available for recovery.
In-flight bytes count unique sent bytes beyond `SND.UNA`, so retransmitting does
not add a second copy to flight size.

`Packet.time` is the **original first-transmit timestamp** on every attempt of
the same logical range. Sink waits therefore include recovery delay. The sender
records the latest attempt time separately; ACKs may echo `Packet.time` for
compatibility, but neither sender trusts that echo as an RTT measurement.
Send transitions register byte state and arm the timer before forwarding data:
a direct synchronous `TCPSink.put()` can safely ACK the new send inline.

## Recovery and RTT/RTO

Each connection has one retransmission timer for its oldest outstanding range.
Sending later new segments does not move that deadline. An advancing cumulative
ACK restarts it from the current time for the remaining oldest range; a completed
flow stops it. Timeout retransmits only that oldest range and doubles the RTO.
Three duplicate ACKs enter fast recovery and retransmit the first hole. A partial
recovery ACK retransmits the next hole while retaining the recovery frontier;
the connection exits recovery when the ACK covers the bytes outstanding at entry.
Partial-recovery retransmissions yield one zero-time SimPy turn so immediate
ACK paths cannot grow the Python call stack with every missing segment. Before
forwarding, the sender checks that the requested range is still missing and has
not been superseded by another attempt.

Both senders conservatively apply Karn's rule: only an ACK for exactly one
complete, never-retransmitted, never-partially-ACKed outstanding segment supplies
an RTT sample. An ACK spanning multiple segments is ambiguous even when its
echoed timestamp looks plausible. Ambiguous ACKs retain the current backed-off
RTO. Zero-delay direct composition can legitimately measure RTT zero.

The estimator follows RFC 6298: the first sample initializes SRTT to RTT and
RTTVAR to RTT/2; later samples update RTTVAR using the previous SRTT before
updating SRTT. RTO is `SRTT + max(G, 4*RTTVAR)`, clamped to 1–60 seconds. Classic
TCP starts at 1 second and uses `G=0.001` seconds. BBR starts with twice its
positive `rtt_estimate`, clamped to the same range; its `granularity` parameter
supplies `G`, defaulting to 0.001 seconds. Backoff also caps at 60 seconds.
The granularity limits the estimator's uncertainty term, not SimPy's clock.

These timer bounds align with the pinned Days CPU model
`9ff20eac16dcdf752510b05cbcf526684dc05146`. Days echoes attempt timing and can
learn an RTT where ns.py's conservative sampling declines an ambiguous ACK.
That is an intentional measurement difference, not a claim of matching RTT
traces. Current Days CPU has no BBR controller; its TCP transport rules provide
shared reference points, while BBR's pacing and delivery-rate model need their
own tests. Congestion-control formula and BBR variant audits belong to Phase 5.

## Application deadlines, pacing, and equal-time events

`Flow.start_time` and `finish_time` are absolute simulation seconds. An omitted
finish time is unbounded. `finish_time` is exclusive for **new transmitted data**:
an application arrival, pacing wake, or ACK at that timestamp cannot emit new
bytes. Already transmitted bytes still retransmit and drain after the deadline.
The finite application volume caps bytes written and emitted; reaching the
new-data deadline may leave an unsent application suffix.

Classic TCP emits new data whenever its application bytes and window permit.
BBR additionally waits for `cc.next_departure_time`; its `cc.pacing_rate` is
bytes/second, so a segment's pacing interval is `segment_bytes / pacing_rate`.
Link rates elsewhere are bits/second and serialize with `8 * bytes / rate_bps`.
BBR's zero pacing rate imposes no pacing delay. Retransmissions are recovery
actions and may occur after the new-data deadline.

SimPy orders equal-time events by priority and insertion order. At an exact
ACK/timeout tie, an ACK processed first cancels the retransmission; a timeout
processed first may emit one fresh attempt before the same-time ACK completes
the flow. Both outcomes must leave no active retransmission behavior. Days
processes arrivals before timeouts at equal timestamps, so this local boundary
can differ; these models do not introduce a new global event-priority engine.
Numeric `env.run(until=t)` also excludes ordinary events at `t`. Tests observe
past the boundary and drain past backed-off deadlines rather than mistaking an
exclusive observation cutoff for missing transport work.
