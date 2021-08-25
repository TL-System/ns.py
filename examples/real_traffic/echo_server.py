import socket
import time
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("listen_port",
                        help="The port this process will listen on.",
                        type=int)

    args = parser.parse_args()

    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind the socket to the port
    server_address = ('localhost', int(args.listen_port))
    print('starting up on %s port %s' % server_address)
    sock.bind(server_address)

    # Listen for incoming connections
    sock.listen(1)
    init_time = time.time()

    while True:
        # Wait for a connection
        print('waiting for a connection')
        connection, client_address = sock.accept()

        try:
            print('connection from', client_address)

            # Receive the data in small chunks and retransmit it
            while True:
                data = connection.recv(64)
                print('received "{}" at time {:.2f}.'.format(
                    data,
                    time.time() - init_time))
                if data:
                    print('sending "{}" back to the client at time {:.2f}'.format(
                        data,
                        time.time() - init_time))
                    connection.sendall(data)
                else:
                    print('no more data from {} at time {:.2f}'.format(
                        client_address,
                        time.time() - init_time))
                    break

        finally:
            # Clean up the connection
            connection.close()
