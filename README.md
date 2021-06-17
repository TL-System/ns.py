# ns.py: A Pythonic Discrete-Event Network Simulator

This discrete-event network simulator is based on [`simpy`](https://simpy.readthedocs.io/en/latest/), which is a general-purpose discrete event simulation framework for Python. `ns.py` is designed to be flexible and reusable, and can be used to connect multiple networking components together easily, including packet generators, network links, switch elements, schedulers, traffic shapers, traffic monitors, and demultiplexing elements.

# Installation

First, launch the terminal and create a new `conda` environment (say, called `ns.py`):

```shell
$ conda update conda
$ conda create -n ns.py python=3.8
$ conda activate ns.py
```

Then, install `ns.py` using `pip`:

```shell
$ pip install ns.py
```

That's it! You can now try to run some examples in the `examples/` directory. More examples will be added as existing components are refined and new components are introduced.

## Current Network Components

The network components that have already been implemented include:

* `Packet`: a simple representation of a network packet, carrying its creation time, size, packet id, flow id, source and destination.

* `PacketDistGenerator`: generates packets according to provided distributions of inter-arrival times and packet sizes.

* `PacketTraceGenerator`: generates packets according to a trace file, with each row in the trace file representing a packet.

* `PacketSink`: receives packets and records delay statistics.

* `Port`: models an output port on a switch with a given rate and buffer size (in either bytes or the number of packets), using the simple tail-drop mechanism to drop packets.

* `REDPort`: models an output port on a switch with a given rate and buffer size (in either bytes or the number of packets), using the Early Random Detection (RED) mechanism to drop packets.

* `Wire`: models a network wire (cable) with its propagation delay following a given distribution. There is no need to model the bandwidth of the wire, as that can be modeled by its upstream `Port` or scheduler.

* `Splitter`: a splitter that simply sends the original packet out of port 1 and sends a copy of the packet out of port 2.

* `NWaySplitter`: an n-way splitter that sends copies of the packet to *n* downstream elements.

* `TrTCM`: a two rate three color marker that marks packets as green, yellow, or red (refer to RFC 2698 for more details).

* `RandomBrancher`: a demultiplexing element that chooses the output port at random.

* `FlowDemux`: a demultiplexing element that splits packet streams by flow ID.

* `TokenBucketShaper`: a token bucket shaper.

* `SPServer`: a Static Priority (SP) scheduler.

* `WFQServer`: a Weighted Fair Queueing (WFQ) scheduler.

* `DRRServer`: a Deficit Round Robin (DRR) scheduler.

* `VirtualClockServer`: a Virtual Clock scheduler (not yet completed).

* `PortMonitor`: records the number of packets in a `Port`. The monitoring interval follows a given distribution.

* `ServerMonitor`: records performance statistics in a scheduling server, such as `WFQServer`, `SPServer`, or `DRRServer`.

## Current utilities

* `TaggedStore`: a sorted `simpy.Store` based on tags (stamps), useful in the implementation of WFQ and Virtual Clock. This may be overkill for static priority queues.

* `Config`: a global singleton instance that reads parameter settings from a configuration file. Use `Config()` to access the instance globally.

## Current Examples (in increasing levels of complexity)

* `basic.py`: a basic example that connects two packet generators to a network wire with a propagation delay distribution, and then to a packet sink.

* `overloaded_switch.py`: an example that contains a packet generator connected to a downstream switch port, which is then connected to a packet sink.

* `mm1.py`: this example shows how to simulate a switching port with exponential packet inter-arrival times and exponentially distributed packet sizes.

* `token_bucket.py`: this example creates a traffic shaper whose bucket size is the same as the packet size, and whose bucket rate is one half the input packet rate.

* `wfq.py`: an example of using the WFQ/virtual clock scheduler.

* `drr.py`: an example of using the Deficit Round Robin (DRR) scheduler.

* `fattree-fifo.py`: an example that shows how to construct and use a FatTree topology for network flow simulation.

## Writing New Network Components

To design and implement new network components in this framework, you will first need to read the [10-minute SimPy tutorial](https://simpy.readthedocs.io/en/latest/simpy_intro/index.html). It literally takes 10 minutes to read, but if that is still a bit too long, you can safely skip the section on *Process Interaction*, as this feature will rarely be used in this network simulation framework.

In the *Basic Concepts* section of this tutorial, pay attention to three simple calls: `env.process()`, `env.run()`, and `yield env.timeout()`. These are heavily used in this network simulation framework.

### Setting up a process

The first is used in our component's constructor to add this component's `run()` method to the `SimPy` environment. For example, in `scheduler/drr.py`:

```python
self.action = env.process(self.run())
```

Keep in mind that not all network components need to be run as a *SimPy* process (more discussions on processes later). While traffic shapers, packet generators, ports (buffers), port monitors, and packet schedulers definitely should be implemented as processes, a flow demultiplexer, a packet sink, a traffic marker, or a traffic splitter do not need to be modeled as processes. They just represent additional processing on packets inside a network.

### Running a process

The second call, `env.run()`, is used by our examples to run the environment after connecting all the network components together. For example, in `examples/drr.py`:

```python
env.run(until=100)
```

This call simply runs the environment for 100 seconds.

### Scheduling an event

The third call, `yield env.timeout()`, schedules an event to be fired sometime in the future. *SimPy* uses an ancient feature in Python that's not well known, *generator functions*, to implement what it called *processes*. The term *process* is a bit confusing, as it has nothing to do with processes in operating systems. In *SimPy*, each process is simply a sequence of timed events, and multiple processes occur concurrently in real-time. For example, a scheduler is a process in a network, and so is a traffic shaper. The traffic shaper runs concurrently with the scheduler, and both of these components run concurrently with other traffic shapers and schedulers in other switches throughout the network.

In order to implement these processes in a network simulation, we almost always use the `yield env.timeout()` call. Here, `yield` uses the feature of generator functions to return an iterator, rather than a value. This is just a fancier way of saying that it *yields* the *process* in *SimPy*, allowing other processes to run for a short while, and it will be resumed at a later time specified by the timeout value. For example, for a Deficit Round Robin (DRR) scheduler to send a packet (in `scheduler/drr.py`), it simply calls:

```python
yield self.env.timeout(packet.size * 8.0 / self.rate)
```

which implies that the scheduler *process* will resume its execution after the transmission time of the packet elapses. A side note: in our network components implemented so far, we assume that the `rate` (or *bandwidth*) of a link is measured in bits per second, while everything else is measured in bytes. As a result, we will need a little bit of a unit conversion here.

What a coincidence: the `yield` keyword in Python in generator functions is the same as the `yield()` system call in an operating system kernel! This makes the code much more readable: whenever a process in *SimPy* needs to wait for a shared resource or a timeout, simply call `yield`, just like calling a system call in an operating system.

**Watch out** for a potential pitfall: Make sure that you call `yield` at least once in *every* path of program execution. This is more important in an infinite loop in `run()`, which is very typical in our network components since the environment can be run for a finite amount of simulation time. For example, at the end of each iteration of the infinite loop in `scheduler/drr.py`, we call `yield`:

```python
yield self.env.timeout(1.0 / self.rate)
```

This will make sure that other processes have a chance to run when there are no packets in the scheduler. This is, on the other hand, not a problem in our Weighted Fair Queueing (WFQ) scheduler (`scheduler/wfq.py`), since we call `yield self.store.get()` to retrieve the next packet for processing, and `self.store` is implemented as a sorted queue. This process will not be resumed after `yield` if there are no packets in the scheduler.

### Sharing resources

The *Shared Resources* section of the 10-minute SimPy tutorial discussed a mechanism to request and release (either automatically or manually) a shared resource by using the `request()` and `release()` calls. In this network simulation framework, we will simplify this by directly calling:

```python
packet = yield store.get()
```

Here, `store` is an instance of `simpy.Store`, which is a simple first-in-first-out buffer containing shared resources in *SimPy*. We initialize one such buffer for each flow in `scheduler/drr.py`:

```python
if not flow_id in self.stores:
    self.stores[flow_id] = simpy.Store(self.env)
```

### Sending packets out

How do we send a packet to a downstream component in the network? All we need to do is to call the component's `put()` function. For example, in `scheduler/drr.py`, we run:

```python
self.out.put(packet)
```

after a timeout expires. Here, `self.out` is initialized to `None`, and it is up to the `main()` program to set up. In `examples/drr.py`, we set the downstream component of our DRR scheduler to a packet sink:

```python
drr_server.out = ps
```

By connecting multiple components this way, a network can be established with packets flowing from packet generators to packet sinks, going through a variety of schedulers, traffic shapers, traffic splitters, and flow demultiplexers.

### Flow identifiers

Flow IDs are assigned to packets when they are generated by a packet generator, which is (optionally) initialized with a specific flow ID. Though this is pretty routine, there is one little catch that one needs to be aware of: we use flow IDs extensively as indices of data structures, such as lists, throughout our framework. For example, in `scheduler/drr.py`, we use flow IDs as indices to look up our lists of deficit counters and quantum values:

```python
self.deficit[flow_id] += self.quantum[flow_id]
```

This is convenient, but it also implies that one cannot use arbitrary flow IDs for the flows going through a network: they must be sequentially generated. Of course, it also implies that these lists will grow larger as flows are established and terminated. Conceptually, one can design a new data structure that maps real flow IDs to indices, and use the mapped indices to look up data structures of *currently active* flows in the network. This, however, adds complexity, which may not be warranted in the current simple design.

