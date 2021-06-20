import re

from ns.packet.packet import Packet


class TracePacketGenerator:
    def __init__(self,
                 env,
                 element_id,
                 filename,
                 initial_delay=0,
                 finish=float('inf'),
                 flow_id=None,
                 rec_flow=False,
                 debug=False):
        self.element_id = element_id
        self.env = env
        self.filename = filename
        self.initial_delay = initial_delay
        self.finish = finish
        self.out = None
        self.flow_id = flow_id
        self.packets_sent = 0
        self.action = env.process(self.run())

        self.rec_flow = rec_flow
        self.time_rec = []
        self.size_rec = []

        self.debug = debug

    def run(self):
        """The generator function used in simulations."""
        yield self.env.timeout(self.initial_delay)

        row_generator = (row for row in open(self.filename))
        last_packet_time = 0

        try:
            while self.env.now < self.finish:
                row = re.split(r"\s+", next(row_generator).rstrip('[\t ]+\n'))
                if flow_id is None:
                    flow_id = int(row[0])
                    packet_id = int(row[1])
                    time = float(row[2])
                    size = int(row[3])
                else:
                    flow_id = self.flow_id
                    packet_id = int(row[0])
                    time = float(row[1])
                    size = int(row[2])

                yield self.env.timeout(max(0, time - last_packet_time))
                last_packet_time = time

                self.packets_sent += 1
                packet = Packet(self.env.now,
                                size,
                                packet_id,
                                src=self.element_id,
                                flow_id=flow_id)
                if self.rec_flow:
                    self.time_rec.append(packet.time)
                    self.size_rec.append(packet.size)

                if self.debug:
                    print(
                        f"Sent packet {packet.packet_id} with flow_id {packet.flow_id} at "
                        f"time {self.env.now}.")

                self.out.put(packet)

        except StopIteration:
            pass
