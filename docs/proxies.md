# Local socket proxies

`ProxyPacketGenerator` listens on localhost; `ProxySink` connects to a destination.
Connect their `out` attributes through ordinary wires, ports, and schedulers.
Use a **plain `simpy.Environment`**, as in `examples/real_traffic/proxy.py`, and
call both proxies' `close()` methods in a `finally` block. The polling process
already waits on wall sockets; adding a RealtimeEnvironment would add another
pacing mechanism. These components are small emulation adapters, not TCP protocol
models or a production proxy server.

## Payload and flow identity

A TCP receive yields a chunk of at most `packet_size` bytes. TCP is a byte stream:
application writes can be split or coalesced, so simulated packet boundaries do
not preserve application messages. UDP receives a whole IPv4 datagram, up to
65,535 bytes of receive capacity, regardless of `packet_size`; a smaller TCP
receive limit must not silently truncate UDP traffic. `Packet.size` is always
the actual payload length in bytes, which makes the simulated link's `8 * size /
rate_bps` serialization calculation account for real bytes. Protocol headers
are not included.

The listening proxy assigns increasing integer flow IDs to TCP connections and
UDP client `(address, port)` pairs. IDs no longer depend on a client's port alone.
Return packets must preserve `flow_id`. The sink owns a separate connected socket
for every flow, including UDP, so replies from the destination retain the correct
identity. UDP address associations and sockets remain until explicit shutdown;
UDP has no EOF signal and this adapter does not add inactivity expiry.

`payload=None` is the TCP EOF marker. It closes the entire flow and is excluded
from sink application-byte/packet statistics. An empty UDP payload `b""` is a
valid datagram, is forwarded, and counts as a zero-byte data packet. TCP half-close
is not supported: client EOF closes its return path even if the server still has
responses in flight. A server EOF is also forwarded as a close marker. Simulator
loss or reordering of TCP chunks is not repaired by an internal retransmission
protocol; use the modeled TCP generator/receiver to study those algorithms.

## Timing and shutdown

Proxy-created packets carry **absolute `time.monotonic()` seconds** in
`packet.realtime`; ordinary packet timestamps remain simulation seconds. At
`put()`, the adapter computes a wall deadline as `packet.realtime + max(0,
env.now - packet.time)`. This prevents delivery before the packet's simulated
path delay has elapsed on the real clock. A normal `Packet` with its default
`realtime=0` is immediately due. Callers supplying `realtime` must use the new
absolute monotonic convention, rather than time relative to one proxy's creation.
The convention works when the two proxies start at different wall times.

The existing SimPy process polls sockets and drains a deadline heap. Equal
send deadlines retain insertion order, and deadlines within a flow cannot move
backwards: accepted data stays ahead of a later close marker. Each poll yields
at least 0.01 simulation seconds, including rounds with ready sockets. Simulation
time catches up to elapsed wall time measured from construction and the initial
`env.now`; it may run ahead when other components advance it. Delayed sends still
wait for their wall deadline. This is approximate emulation with polling latency,
not nanosecond real-time scheduling. Heavy traffic or slow sockets can increase
latency. Run all proxy methods on the simulation thread.

TCP uses `sendall()` and a one-second socket timeout. A TCP send/receive error
closes that flow, cancels its queued work, and emits a close marker.
A timed-out `sendall()` can already have written a prefix, so the flow terminates
rather than replaying bytes. Failed connects close the new descriptor and propagate
the exception. The socket timeout bounds connect/send after address resolution;
system hostname resolution itself is outside that bound. For bounded local runs,
use a numeric loopback destination and an explicitly configured local server.

`close()` is idempotent: it immediately closes owned descriptors, clears UDP
associations, and cancels all queued sends. Later `put()` calls do nothing. The
SimPy polling process terminates at its next scheduled wakeup; no background
threads or timer callbacks exist. Stopping `env.run()` alone does not close
sockets, which is why the example uses `finally`. Socket resources grow with
active flows; this adapter adds no admission limits or server framework.

`ProxySink` reuses `PacketSink` for simulated arrivals, waiting times, byte counts,
and independent per-hop snapshots. These statistics describe arrival at the
simulated sink, including payloads whose eventual real send fails; they are not
proof of remote application consumption. Current Days CPU has no real-socket
counterpart, so proxy validation uses bounded local sockets and independent
invariants rather than a claimed cross-simulator match.
