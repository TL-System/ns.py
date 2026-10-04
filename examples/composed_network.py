"""A finite Reno flow recovers congestion through a shaped, slow data path.

Run with: uv run --locked python examples/composed_network.py
No randomness, sockets, display, or command-line configuration is required.
"""

import simpy

from ns.flow.cc import TCPReno
from ns.flow.flow import Flow
from ns.packet.tcp_generator import TCPPacketGenerator
from ns.packet.tcp_sink import TCPSink
from ns.port.monitor import PortMonitor
from ns.port.port import Port
from ns.port.wire import Wire
from ns.shaper.token_bucket import TokenBucketShaper


def main():
    env = simpy.Environment()
    flow = Flow(7, "source", "receiver", size=1001, finish_time=.5)
    sender = TCPPacketGenerator(env, flow, TCPReno(mss=300, cwnd=1200))
    receiver = TCPSink(env)

    # Data: sender -> shaper -> bottleneck -> propagation -> receiver.
    # Tokens are bytes; 1200 bits/s replenishes 150 bytes/s. The full bucket
    # initially admits all three 300-byte segments and the 101-byte tail.
    shaper = TokenBucketShaper(env, rate=1200, bucket_size=1001)
    # This capacity includes service. Only two initial segments fit, so the
    # third segment and tail drop and must return as fresh TCP attempts.
    bottleneck = Port(env, rate=24000, qlimit=600, limit_bytes=True)
    data_wire = Wire(env, lambda: .01)
    ack_wire = Wire(env, lambda: .01)
    monitor = PortMonitor(env, bottleneck, lambda: .05, True)
    sender.out = shaper
    shaper.out = bottleneck
    bottleneck.out = data_wire
    data_wire.out = receiver
    receiver.out = ack_wire
    ack_wire.out = sender

    env.run(until=.3)
    print(f"Initial burst: {bottleneck.packets_dropped} drops; "
          f"{receiver.bytes_delivered} of {flow.size} application bytes delivered.")
    # New sends end at .5 s. Already-sent bytes still recover after that time:
    # the first retry waits for tokens, then the short tail needs another timeout.
    env.run(until=5)
    assert receiver.bytes_delivered == sender.last_ack == flow.size
    assert sender.bytes_in_flight == bottleneck.byte_size == 0
    assert monitor.sizes[-1] == monitor.sizes_byte[-1] == 0
    assert sender.timer.stopped
    print(f"Recovery: {receiver.bytes_delivered} bytes delivered and acknowledged; "
          f"bottleneck peak {max(monitor.sizes_byte)} bytes, final queue empty.")


if __name__ == "__main__":
    main()
