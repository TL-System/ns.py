class Flow:
    def __init__(self,
                 fid,
                 src,
                 dst,
                 size=None,
                 start_time=None,
                 finish_time=None,
                 arrival_dist=None,
                 pkt_gen=None,
                 pkt_sink=None) -> None:
        self.fid = fid
        self.src = src
        self.dst = dst
        self.size = size
        self.start_time = start_time
        self.finish_time = finish_time
        self.arrival_dist = arrival_dist
        self.pkt_gen = pkt_gen
        self.pkt_sink = pkt_sink

        self.path = None

    def __repr__(self) -> str:
        return f"Flow {self.fid} on {self.path}"
