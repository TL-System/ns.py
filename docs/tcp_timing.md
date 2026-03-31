# TCP Timing Contract

This note captures the transport semantics the TCP rewrite relies on.

- `TCPSink` tracks the cumulative ACK frontier, `RCV.NXT`, from the contiguous
  prefix only.
- `TCPPacketGenerator` owns logical segment state keyed by segment start
  sequence number.
- Every send or retransmit emits a fresh `Packet` object derived from that
  logical segment state.
- `Packet.time` on TCP data packets is the original first-transmit timestamp
  used by sinks for end-to-end latency accounting.
- RTT and RTO updates are sender-owned and conservative.
- In this phase, the sender does not guess RTT from retransmitted or ambiguous
  ACKs.
- The transport rewrite assumes no TCP timestamps, no SACK, and no delayed-ACK
  modeling.

## Why this exists

The classic TCP rewrite splits timing ownership between packet objects,
receiver ACK logic, and sender metadata. This note gives a stable reference for
the intended split so later changes can preserve the same contract.
