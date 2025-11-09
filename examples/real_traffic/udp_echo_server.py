"""A simple UDP echo server."""

import argparse
import socketserver


class MyUDPHandler(socketserver.BaseRequestHandler):
    """
    This class works in a similar way to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        print(f"{self.client_address} wrote: ")
        print(data)
        socket.sendto(data, self.client_address)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "listen_port", help="The port this process will listen on.", type=int
    )

    args = parser.parse_args()
    with socketserver.UDPServer(
        ("localhost", int(args.listen_port)), MyUDPHandler
    ) as server:
        server.serve_forever()
