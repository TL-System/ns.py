import argparse
import socket

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("server_host", help="The remote host to connect to.")
    parser.add_argument("server_port",
                        help="The remote port to connect to.",
                        type=int)
    args = parser.parse_args()

    message = "This is a new message.  It will be echoed."

    # SOCK_DGRAM is the socket type to use for UDP sockets
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Unlike TCP, there is is no connect() call; UDP has no connections.
    # Instead, data is directly sent to the recipient via sendto().
    sock.sendto(bytes(message + "\n", "utf-8"),
                (args.server_host, int(args.server_port)))
    received = str(sock.recv(1024), "utf-8")

    print("Sent:     {}".format(message))
    print("Received: {}".format(received))
