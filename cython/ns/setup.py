#!/usr/bin/env python
from setuptools import setup, Extension

from Cython.Build import cythonize

ext_modules = cythonize(
    [
        Extension("ns.demux.fib_demux", ["ns/demux/fib_demux.py"]),
        Extension("ns.demux.flow_demux", ["ns/demux/flow_demux.py"]),
        Extension("ns.demux.random_demux", ["ns/demux/random_demux.py"]),
        Extension("ns.flow.cc", ["ns/flow/cc.py"]),
        Extension("ns.flow.cubic", ["ns/flow/cubic.py"]),
        Extension("ns.flow.flow", ["ns/flow/flow.py"]),
        Extension("ns.packet.dist_generator", ["ns/packet/dist_generator.py"]),
        Extension("ns.packet.packet", ["ns/packet/packet.py"]),
        Extension("ns.packet.proxy_generator", ["ns/packet/proxy_generator.py"]),
        Extension("ns.packet.proxy_sink", ["ns/packet/proxy_sink.py"]),
        Extension("ns.packet.sink", ["ns/packet/sink.py"]),
        Extension("ns.packet.tcp_generator", ["ns/packet/tcp_generator.py"]),
        Extension("ns.packet.tcp_sink", ["ns/packet/tcp_sink.py"]),
        Extension("ns.packet.trace_generator", ["ns/packet/trace_generator.py"]),
        Extension("ns.port.monitor", ["ns/port/monitor.py"]),
        Extension("ns.port.port", ["ns/port/port.py"]),
        Extension("ns.port.red_port", ["ns/port/red_port.py"]),
        Extension("ns.port.wire", ["ns/port/wire.py"]),
        Extension("ns.scheduler.drr", ["ns/scheduler/drr.py"]),
        Extension("ns.scheduler.monitor", ["ns/scheduler/monitor.py"]),
        Extension("ns.scheduler.sp", ["ns/scheduler/sp.py"]),
        Extension("ns.scheduler.virtual_clock", ["ns/scheduler/virtual_clock.py"]),
        Extension("ns.scheduler.wfq", ["ns/scheduler/wfq.py"]),
        Extension("ns.shaper.token_bucket", ["ns/shaper/token_bucket.py"]),
        Extension(
            "ns.shaper.two_rate_token_bucket", ["ns/shaper/two_rate_token_bucket.py"]
        ),
        Extension("ns.switch.switch", ["ns/switch/switch.py"]),
        Extension("ns.topos.fattree", ["ns/topos/fattree.py"]),
        Extension("ns.topos.utils", ["ns/topos/utils.py"]),
        Extension(
            "ns.utils.generators.MAP_MSP_generator",
            ["ns/utils/generators/MAP_MSP_generator.py"],
        ),
        Extension(
            "ns.utils.generators.pareto_onoff_generator",
            ["ns/utils/generators/pareto_onoff_generator.py"],
        ),
        Extension("ns.utils.config", ["ns/utils/config.py"]),
        Extension("ns.utils.misc", ["ns/utils/misc.py"]),
        Extension("ns.utils.splitter", ["ns/utils/splitter.py"]),
        Extension("ns.utils.taggedstore", ["ns/utils/taggedstore.py"]),
        Extension("ns.utils.timer", ["ns/utils/timer.py"]),
    ],
    language_level=3,
)

setup(ext_modules=ext_modules)
