import socket


def get_constants(prefix):
    """Create a dictionary mapping socket module constants to their names."""
    return dict(
        (getattr(socket, n), n) for n in dir(socket) if n.startswith(prefix))


families = get_constants('AF_')
types = get_constants('SOCK_')
protocols = get_constants('IPPROTO_')

# Create a TCP/IP socket
sock = socket.create_connection(('localhost', 5000))

try:

    # Send data
    message = 'This is the message.  It will be repeated.'
    print('sending "%s"' % message)
    sock.sendall(bytes(message, 'utf-8'))

    amount_received = 0
    amount_expected = len(message)

    while amount_received < amount_expected:
        data = sock.recv(64)
        amount_received += len(data)
        print('received "%s"' % data)

finally:
    print('closing socket')
    sock.close()
