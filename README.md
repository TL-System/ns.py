# ns.py: A Pythonic Discrete-Event Network Simulator

This discrete-event network simulator is based on [`simpy`](https://simpy.readthedocs.io/en/latest/), which is a general-purpose discrete event simulation framework for Python. `ns.py` is designed to be flexible and reusable, and can be used to connect multiple networking components together easily, including packet generators, network links, switch elements, schedulers, traffic shapers, traffic monitors, and demultiplexing elements.

Use it to study packet timing, scheduling, queue occupancy, and congestion
control by connecting small components through `out` and `put(packet)`. The
models deliberately omit some production protocol mechanisms; read the
[model notes](docs/model_notes.md) before interpreting results as TCP, WFQ, RED,
or BBR behavior. The [audit inventory](docs/modernization.md#component-inventory)
links each module to its tests and reference evidence.

## Installation

### From PyPI

```shell
pip install ns.py
```

### Local development with uv

The development target is Python 3.14. Python 3.14.1 is excluded to match
NetworkX's supported interpreter versions.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it's not already on your machine.
2. Sync the project and provision a Python 3.14 virtual environment:

   ```shell
   uv sync --locked
   ```

3. Run commands through `uv run` so they pick up the synced environment. For example:

   ```shell
   uv run --locked python examples/basic.py
   ```

`uv sync --locked` installs `ns.py` in editable mode along with its runtime
dependencies and pytest. Use `uv run --locked` for tests and examples to keep
the environment aligned with the checked-in lockfile. Use `uv lock --upgrade`
when refreshing packages, then review the lockfile and re-run the checks below.
`uv build` builds the wheel and source distribution in an isolated build
environment.

## Current network components

The network components that have already been implemented include:

* `Packet`: a simple representation of a network packet, carrying its creation time, size, packet id, flow id, source and destination.

* `DistPacketGenerator`: generates packets according to provided distributions of inter-arrival times and packet sizes.

* `TracePacketGenerator`: generates packets according to a trace file, with each row in the trace file representing a packet.

* `TCPPacketGenerator`: models a cumulative-ACK TCP byte stream with configurable congestion control.
  See [`docs/tcp_timing.md`](docs/tcp_timing.md) for the sender/receiver
  segmentation, retransmission, application-deadline, and timing contract.

* `BBRPacketGenerator`: models a paced TCP sender using the [educational BBR controller](docs/bbr.md).

* `ProxyPacketGenerator`: forwards real TCP receive chunks or UDP datagrams into simulation packets whose sizes equal the received payload lengths.

* `PacketSink`: receives packets and records delay statistics.

* `TCPSink`: receives packets, records delay statistics, and produces acknowledgements back to a TCP sender.

* `ProxySink`: forwards simulated payloads to a real TCP or UDP server and returns responses through the simulation; see [proxy timing and lifecycle](docs/proxies.md).

* `Port`: an output port on a switch with a given rate and buffer size (in either bytes or the number of packets), using the simple tail-drop mechanism to drop packets.

* `REDPort`: an output port on a switch with a given rate and buffer size (in either bytes or the number of packets), using the Random Early Detection (RED) mechanism to drop packets.

* `Wire`: a network wire (cable) with its propagation delay following a given distribution. There is no need to model the bandwidth of the wire, as that can be modeled by its upstream `Port` or scheduling server.

* `Splitter`: a splitter that simply sends the original packet out of port 1 and sends a copy of the packet out of port 2.

* `NWaySplitter`: an n-way splitter that sends copies of the packet to *n* downstream elements.

* `TrTCM`: a two rate three color marker that marks packets as green, yellow, or red (refer to RFC 2698 for more details).

* `RandomDemux`: a demultiplexing element that chooses the output port at random.

* `FlowDemux`: a demultiplexing element that splits packet streams by flow ID.

* `FIBDemux`: a demultiplexing element that uses a Forwarding Information Base (FIB) to make packet forwarding decisions based on flow IDs.

* `TokenBucketShaper`: a token bucket shaper.

* `TwoRateTokenBucketShaper`: a two-rate three-color token bucket shaper with both committed and peak rates/burst sizes.

* `SPServer`: a Static Priority (SP) scheduler.

* `WFQServer`: a Weighted Fair Queueing (WFQ) scheduler.

* `DRRServer`: a Deficit Round Robin (DRR) scheduler.

* `VirtualClockServer`: a Virtual Clock scheduler.

* `SimplePacketSwitch`: a packet switch with a FIFO bounded buffer on each of the outgoing ports.

* `FairPacketSwitch`: a fair packet switch with a choice of a WFQ, DRR, Static Priority or Virtual Clock scheduler, as well as bounded buffers, on each of the outgoing ports. It also shows an example how a simple hash function can be used to map tuples of (flow_id, node_id, and port_id) to class IDs, and then use the parameter `flow_classes` to activate class-based scheduling rather than flow-based scheduling.

* `PortMonitor`: records the number of packets in a `Port`. The monitoring interval follows a given distribution.

* `ServerMonitor`: records performance statistics in a scheduling server, such as `WFQServer`, `VirtualClockServer`, `SPServer`, or `DRRServer`.

## Current utilities

* `TaggedStore`: a sorted `simpy.Store` based on tags, useful in the implementation of WFQ and Virtual Clock.

* `Config`: a global singleton instance that reads parameter settings from a configuration file. Use `Config()` to access the instance globally.

## Current examples (in increasing levels of complexity)

* `basic.py`: A basic example that connects two packet generators to a network wire with a propagation delay distribution, and then to a packet sink. It showcases `DistPacketGenerator`, `PacketSink`, and `Wire`.

* `overloaded_switch.py`: an example that contains a packet generator connected to a downstream switch port, which is then connected to a packet sink. It showcases `DistPacketGenerator`, `PacketSink`, and `Port`.

* `mm1.py`: this example shows how to simulate a port with exponential packet inter-arrival times and exponentially distributed packet sizes. It showcases `DistPacketGenerator`, `PacketSink`, `Port`, and `PortMonitor`.

* `tcp.py`: this example shows how a two-hop simple network from a sender to a receiver, via a simple packet forwarding switch, can be configured, and how acknowledgment packets can be sent from the receiver back to the sender via the same switch. The sender uses a TCP as its transport protocol, and the congestion control algorithm is configurable (such as TCP Reno or TCP CUBIC). It showcases `TCPPacketGenerator`, `CongestionControl`, `TCPSink`, `Wire`, and `SimplePacketSwitch`.

* `token_bucket.py`: this example creates a traffic shaper whose bucket size is the same as the packet size, and whose bucket rate is one half the input packet rate. It showcases `DistPacketGenerator`, `PacketSink`, and `TokenBucketShaper`.

* `two_rate_token_bucket.py`: this example creates a two-rate three-color traffic shaper. It showcases `DistPacketGenerator`, `PacketSink`, and `TwoRateTokenBucketShaper`.

* `static_priority.py`: this example shows how to use two Static Priority (SP) schedulers to construct a more complex two-layer scheduler, turning on `zero_downstream_buffer` for the upstream scheduler and `zero_buffer` for the downstream one. It showcases `DistPacketGenerator`, `PacketSink`, and `SPServer`.

* `wfq.py`: this example shows how to use the Weighted Fair Queueing (WFQ) scheduler, and how to use a server monitor to record performance statistics with a finer granularity using a sampling distribution. It showcases `DistPacketGenerator`, `PacketSink`, `Splitter`, `WFQServer`, and `ServerMonitor`.

* `virtual_clock.py`: this example shows how to use the Virtual Clock scheduler, and how to use a server monitor to record performance statistics with a finer granularity using a sampling distribution. It showcases `DistPacketGenerator`, `PacketSink`, `Splitter`, `VirtualClockServer`, and `ServerMonitor`.

* `drr.py`: this example shows how to use the Deficit Round Robin (DRR) scheduler. It showcases `DistPacketGenerator`, `PacketSink`, `Splitter` and `DRRServer`.

* `two_level_drr.py`, `two_level_wfq.py`, `two_level_sp.py`: these examples have shown how to construct a two-level topology consisting of Deficit Round Robin (DRR), Weighted Fair Queueing (WFQ) and Static Priority (SP) servers. They also show how to use strings for flow IDs and to use dictionaries to provide per-flow weights to the DRR, WFQ, or SP servers, so that group IDs and per-group flow IDs can be easily used to construct globally unique flow IDs.

* `red_wfq.py`: this example shows how to combine a Random Early Detection (RED) buffer (or a tail-drop buffer) and a WFQ server. The RED or tail-drop buffer serves as an upstream input buffer, configured to recognize that its downstream element has a zero-buffer configuration. The WFQ server is initialized with zero buffering as the downstream element after the RED or tail-drop buffer. Packets will be dropped when the downstream WFQ server is the bottleneck. It showcases `DistPacketGenerator`, `PacketSink`, `Port`, `REDPort`, `WFQServer`, and `Splitter`, as well as how `zero_buffer` and `zero_downstream_buffer` can be used to construct more complex network elements using elementary elements.

* `fattree.py`: an example that shows how to construct and use a FatTree topology for network flow simulation. It showcases `DistPacketGenerator`, `PacketSink`, `SimplePacketSwitch`, and `FairPacketSwitch`. If per-flow fairness is desired, `FairPacketSwitch` would be used, along with Weighted Fair Queueing, Deficit Round Robin, or Virtual Clock as the scheduling discipline at each outgoing port of the switch.

## Emulation mode

Similar to the emulation mode in the ns-3 simulator, `ns.py` supports an *emulation mode* that serves as a proxy between a real-world client (such as a modern web browser) and a real-world server (such as a node.js webserver). All incoming traffic from a real-world client are handled by the `ProxyPacketGenerator`, sent via a simulated network topology, and forwarded by the `ProxySink` to a real-world server. Here is a high-level overview of the design of `ns.py`'s emulation mode:

<p align="center">
  <img src="https://github.com/TL-System/ns.py/blob/main/docs/emulation/emulation_mode.svg" alt="High-level overview of ns.py's emulation mode"/>
</p>

`examples/real_traffic/proxy.py` has been provided as an example that shows how a real-world client and server can communicate using a simulated network environment as the proxy, and how `ProxyPacketGenerator` and `ProxySink` are to be used to achieve this objective.

The adapters use a plain SimPy environment with cooperative socket polling.
Call both proxies' `close()` methods in `finally` after a run; stopping the
environment alone does not close sockets. TCP receives are stream chunks, not
application messages, and simulated loss is not repaired by a proxy-internal TCP
model. See [Local socket proxies](docs/proxies.md) for the supported behavior.

### Testing the emulation mode with simple TCP and UDP echo servers

A simple echo client and echo server have been provided for an example demonstration how the proxy works. To run this example with the provided echo client and echo server, start the server first:

```shell
python examples/real_traffic/tcp_echo_server.py 10000
```

The TCP echo server will listen on port 10000 on `localhost`.

Now run the provided simple example for a TCP `ns.py` proxy:

```shell
python examples/real_traffic/proxy.py 5000 localhost 10000 tcp
```

This TCP proxy will now listen on port 5000, and redirects all traffic to `localhost:10000`, which is where the TCP echo server is.

Finally, run the TCP echo client:

```shell
python examples/real_traffic/tcp_echo_client.py localhost 5000
```

It will send one simple message to port 5000, where the TCP proxy is.

To use an UDP proxy instead, first run the UDP echo server, which listens on port 10000 on `localhost`:

```shell
python examples/real_traffic/udp_echo_server.py 10000
```

Then run the UDP `ns.py` proxy on port 5000, asking it to redirect all traffic to `localhost:10000`, where the UDP echo server is.

```shell
python examples/real_traffic/proxy.py 5000 localhost 10000 udp
```

Finally, run the UDP echo client:

```shell
python examples/real_traffic/udp_echo_client.py localhost 5000 Hello World
```

### Testing the emulation mode with a simple HTTPS server

A simple HTTPS server has been provided in `examples/real_traffic`. To use it to test the emulation mode, you will need to generate a self-signed server certificate first:

```shell
openssl req -new -x509 -keyout server_cert.pem -out server_cert.pem -days 365 -nodes
```

Then run the HTTPS server:
```shell
python examples/real_traffic/https_server.py 4443 server_cert.pem
```

Now you can run the `ns.py` proxy with the HTTPS server as its destination:

```shell
python examples/real_traffic/proxy.py 5000 localhost 4443
```

Finally, run a `curl` HTTPS client to connect to the HTTP server:

```shell
curl -v https://localhost:5000 --insecure
```

## Writing new network components

Start with the [SimPy tutorial](https://simpy.readthedocs.io/en/latest/simpy_intro/index.html).
Components that wait for packets or model elapsed time use generator functions
as SimPy processes. A constructor typically registers its process:

```python
self.action = env.process(self.run())
```

A process yields an event, such as `store.get()` or `env.timeout(delay)`, and
resumes when that event completes. Other processes can then run at the same
simulation time or advance the simulated clock. This concurrency uses simulated
time; ordinary simulations need not wait for wall-clock time to pass.

A FIFO serializer can express its timing directly:

```python
packet = yield self.store.get()
yield self.env.timeout(packet.size * 8.0 / self.rate)
self.out.put(packet)
```

Packet sizes are bytes and link rates are bits/second, so the factor of eight
converts bytes to bits. Most clocks use seconds. BBR pacing and `StackDelayer`
use bytes/second instead; check each component's documented units.

Each repeating process path must yield an event. An idle server should wait for
work; repeatedly yielding zero-time events without eventual time progress can
still stall a simulation. Schedulers may use a zero-time selection wait to admit
already scheduled same-time arrivals, then perform nonpreemptive service. WFQ
and Virtual Clock wake separately from selection so an idle heap `get()` cannot
reserve a packet before other same-time arrivals are considered.

Demultiplexers, splitters, sinks, and markers normally act synchronously inside
`put()` and need no process of their own. A downstream `put()` may call back
immediately, so register send/accounting state before forwarding. Connect an
output before running the environment, for example:

```python
generator.out = port
port.out = sink
env.run(until=100)
```

Numeric `env.run(until=100)` observes events before time 100; ordinary events
exactly at that boundary remain pending. Use a finite source and `env.run()` to
drain a network with no forever-running monitor. See
[`examples/composed_network.py`](examples/composed_network.py) for a finite
composition and [model notes](docs/model_notes.md) for shared-buffer ownership.

Flow IDs identify routes and statistics. Schedulers use `flow_classes(packet)`
to map flows to scheduling classes without rewriting `packet.flow_id`. Lists
index configured integer class IDs; dictionaries support named or sparse class
IDs. Flows mapped to one class share its FIFO, priority, or finish-tag history,
according to the chosen discipline.

## Running Tests

Run the regression suite with:

```bash
uv run pytest -q
```

CI also runs the finite basic, TCP, FatTree, and composed-network scenarios with Matplotlib's
headless `Agg` backend and a 90-second timeout per process:

```shell
uv run --locked python scripts/smoke_examples.py
uv build
```

Real-traffic proxy and server examples need their local client/server setup
described above and are run separately.
