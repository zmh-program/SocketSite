from typing import *
import socket


class AbstractSocketServerClient(object):
    def __init__(self, sock: socket.socket, addr):
        self.socket = sock
        self.addr = addr
        self.is_alive = True

    def send(self, data: bytes):
        try:
            self.socket.send(data)
        except socket.error:
            self.is_alive = False

    def close(self):
        self.socket.close()


class AbstractSocketServer(object):
    client_type = AbstractSocketServerClient

    def __init__(self, addr: Tuple[str, int], backlog: int = 20):
        self.addr = addr
        self.backlog = backlog
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(self.addr)
        self.clients: List[AbstractSocketServerClient] = []

    @property
    def alive_socket(self) -> Iterable[AbstractSocketServerClient]:
        return filter(lambda client: client.is_alive, self.clients)

    def reset_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(self.addr)
        self.clients = []

    def append_socket(self, sock, addr):
        self.clients.append(self.client_type(sock, addr))

    def listen(self):
        self.socket.listen(self.backlog)
        while True:
            self.append_socket(*self.socket.accept())
