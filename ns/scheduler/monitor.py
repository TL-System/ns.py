class ServerMonitor:
    def __init__(self,
                 env,
                 server,
                 dist,
                 total_flows,
                 pkt_in_service_included=False) -> None:

        self.server = server
        self.env = env
        self.dist = dist
        self.total_flows = total_flows

        self.sizes = {}
        self.byte_sizes = {}

        self.action = env.process(self.run())
        self.pkt_in_service_included = pkt_in_service_included

    def run(self):
        while True:
            yield self.env.timeout(self.dist())

            for flow_id in range(self.total_flows):
                total = self.server.size(flow_id)
                total_bytes = self.server.byte_size(flow_id)

                if self.pkt_in_service_included:
                    if self.server.packet_in_service() is not None:
                        if self.server.pkt_in_service().flow_id == flow_id:
                            total += 1
                            total_bytes += self.server.packet_in_service().size

                if flow_id in self.sizes:
                    self.sizes[flow_id].append(total)
                    self.byte_sizes[flow_id].append(total_bytes)
                else:
                    self.sizes[flow_id] = [total]
                    self.byte_sizes[flow_id] = [total_bytes]
