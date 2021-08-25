""" A simple HTTPS server. """
import argparse
import ssl
from http.server import HTTPServer, SimpleHTTPRequestHandler

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("listen_port",
                        help="The port this process will listen on.",
                        type=int)
    parser.add_argument("cert_file",
                        help="The server certificate file.",
                        type=str)

    args = parser.parse_args()

    httpd = HTTPServer(('localhost', int(args.listen_port)),
                       SimpleHTTPRequestHandler)
    ssl_context = ssl.SSLContext()
    # If set to True, only the hostname that matches the certificate will be accepted
    ssl_context.check_hostname = False
    ssl_context.load_cert_chain(certfile=args.cert_file)
    with ssl_context.wrap_socket(httpd.socket, server_side=True) as ssock:
        httpd.socket = ssock
        httpd.serve_forever()
