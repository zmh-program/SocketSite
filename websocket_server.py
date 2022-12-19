import asyncio
import pickle
from typing import *
import websockets
from websockets.legacy import server


class AsyncServerClient(object):
    def __init__(self, websocket: server.WebSocketServerProtocol, parent):
        self.websocket = websocket
        self.parent: AsyncServer = parent
        self.is_alive = False

    async def listen(self):
        self.is_alive = True
        async for message in self.websocket:
            await self.parent.receive_from_websocket(self, message)
        self.is_alive = False

    @staticmethod
    def recv_pickle(_pickle):
        return pickle.loads(_pickle)

    async def send(self, message) -> bool:
        if self.is_alive:
            await self.websocket.send(message)
            return True
        return False

    async def send_pickle(self, obj):
        return await self.send(pickle.dumps(obj))


class AsyncServer(object):
    client_type = AsyncServerClient

    def __init__(self, addr: Tuple[str, int], allow_hosts=None):
        self.addr = addr
        self.host, self.port = addr
        self.loop = asyncio.new_event_loop()
        self.clients: List[AsyncServerClient] = []
        self.is_alive = False
        self.allow_hosts = set(allow_hosts or [self.host, "localhost", "127.0.0.1"])

    @property
    def alive_socket(self) -> Iterable[AsyncServerClient]:
        return iter(self.clients)

    def __iter__(self):
        return iter(self.clients)

    def __del__(self):
        self.clients = []

    def add_client(self, websocket: server.WebSocketServerProtocol):
        #  host validate
        host = websocket.remote_address[0]
        if host in self.allow_hosts:
            client = self.client_type(websocket, self)
            self.clients.append(client)
            return client.listen()
        else:
            websocket.close()

    async def _listen(self):
        self.is_alive = True
        async with websockets.serve(self.add_client, self.host, self.port, loop=self.loop):
            await asyncio.Future()
        self.is_alive = False

    def listen(self):
        self.loop.run_until_complete(self._listen())

    async def group_send(self, message):
        _clean_clients = []
        for client in self.clients:
            if not await client.send(message):
                _clean_clients.append(client)
        return tuple(map(self.clients.remove, _clean_clients))

    async def receive_from_websocket(self, client: AsyncServerClient, message):
        # await self.group_send(message)
        pass


if __name__ == "__main__":
    _server = AsyncServer(("127.0.0.1", 8000))
    _server.listen()
