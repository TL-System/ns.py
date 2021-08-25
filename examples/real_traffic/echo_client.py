import socket
import time

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument("server_host", help="The remote host to connect to.")
    parser.add_argument("server_port",
                        help="The remote port to connect to.",
                        type=int)
    args = parser.parse_args()

    # Connecting to a host
    sock = socket.create_connection((args.server_host, int(args.server_port)))
    init_time = time.time()

    try:
        message = 'This is a new message.  It will be echoed.'
        print('Sent "{}" at time {:.2f}.'.format(message, time.time() - init_time))
        sock.sendall(bytes(message, 'utf-8'))

        amount_received = 0
        amount_expected = len(message)

        while amount_received < amount_expected:
            data = sock.recv(64)
            amount_received += len(data)
            print('Received "{}" at time {:.2f}.'.format(data, time.time() - init_time))

    finally:
        print('Disconnecting.')
        sock.close()
