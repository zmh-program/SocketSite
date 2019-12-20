import pickle
from websockets.legacy import server
import socket
import threadpool
from typing import *
import websockets
import asyncio
import multiprocessing
from typing import Type
import threading

SITE_HOST = "127.0.0.1"


def is_open_port(host: str, port: int) -> Tuple[int, bool]:
    """tcp detection function"""
    return port, not not socket.socket().connect_ex((host, port))


def get_not_open_ports(host: str, ports: List[int]) -> List[int]:
    """
    Get the ports that are not open
    :param host: IP host (str)
    :param ports: ports (list)
    :return: the ports that are not open (list)
    """

    pool = threadpool.ThreadPool(len(ports))
    responses = []
    tuple(map(
        pool.putRequest,
        threadpool.makeRequests(
            is_open_port,
            [((host, port), ()) for port in ports],
            callback=lambda request, response: responses.append(response[0]) if not response[1] else None,
        ),
    ))

    pool.wait()
    responses.sort()

    return responses


def _exec_detect_port(host: str, port: int, stride: int, max_limit: int) -> Tuple[bool, int]:
    while 0 <= port <= max_limit:
        if socket.socket().connect_ex((host, port)):
            return True, port
        port += stride
    return False, 0


def get_sample_open_ports(host: str, num: int, min_limit: int = 0, max_limit: int = 65535) -> List[Tuple[int]]:
    assert min_limit <= (min_limit + num - 1) <= max_limit, \
        f"Make sure the port range ({min_limit}~{max_limit}, total {num}) is between min(0) and max(65535)!"
    pool = threadpool.ThreadPool(num)
    responses = []
    tuple(map(
        pool.putRequest,
        threadpool.makeRequests(
            _exec_detect_port,
            [((host, min_limit + x, num, max_limit), ()) for x in range(num)],
            callback=lambda request, response: responses.append(response[1]) if response[0] else None,
        ),
    ))

    pool.wait()
    responses.sort()

    assert len(responses) == num, f"Insufficient available ports ({num})! Number of available ports {len(responses)}."
    return responses


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


class AsyncClient(object):
    def __init__(self, addr, loop=None):
        self.host, self.port = addr
        self.addr = addr
        self.loop = loop or asyncio.new_event_loop()
        self.websocket = None

    async def _listen(self):
        async with websockets.connect(self.url, loop=self.loop) as self.websocket:
            async for message in self.websocket:
                await self.receiveEvent(message)

    def listen(self):
        return asyncio.run_coroutine_threadsafe(self._listen(), self.loop)

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/"

    async def receiveEvent(self, message):
        pass

    async def send(self, message: Union[str, bytes]):
        return await self.websocket.send(message)


class BaseProcessApplicationServer(multiprocessing.Process):
    def __init__(self, port: int):
        super().__init__()
        self.ws_thread = None
        self.server = None
        self.port = port

        self.server = AsyncServer((SITE_HOST, self.port))
        #  不从此处初始化self.server的原因:
        #   File "C:\ProgramData\Anaconda3\lib\multiprocessing\popen_spawn_win32.py", line 93, in __init__
        #     reduction.dump(process_obj, to_child)
        #   File "C:\ProgramData\Anaconda3\lib\multiprocessing\reduction.py", line 60, in dump
        #     ForkingPickler(file, protocol).dump(obj)
        # AttributeError: Can't pickle local object 'WeakSet.__init__.<locals>._remove'
        #
        #  我猜原因应该是 process之间不共享内存, 因而需要再启动一个python子进程, 但是再次过程中,
        #  实例中的 AsyncServer(中 _weakrefset.WeakSet的_remove方法)
        #  不能被pickle和反pickle, 因此抛出异常.
        #
        #  那知道原因了就好办了, 直接在子进程中运行的函数中 创建套接字的实例, 就没有问题了.

    def run_process(self):
        pass

    def run(self):
        super().run()
        self.server = AsyncServer((SITE_HOST, self.port))
        self.ws_thread = threading.Thread(target=self.server.listen)
        self.ws_thread.setDaemon(True)
        self.ws_thread.start()
        self.run_process()


class BaseAsyncApplicationClient(AsyncClient):
    def __init__(self, port, loop):
        super().__init__(addr=(SITE_HOST, port), loop=loop)
        self.listen()


class SiteApplication(object):
    port: int
    process_application = BaseProcessApplicationServer
    async_client = BaseAsyncApplicationClient

    def __init__(self, loop):
        assert isinstance(self.port, int)

        if is_open_port(SITE_HOST, self.port):
            self.app = self.process_application(self.port)
            self.app.start()
        self.client = self.async_client(self.port, loop)


class ApplicationManager(object):
    def __init__(self):
        self.apps = []
        self.loop = asyncio.new_event_loop()

    def register(self, _exec_cls: Type[SiteApplication]):
        _cls = _exec_cls(self.loop)
        self.apps.append(_cls)
        return _cls

    def run(self):
        self.loop.run_forever()


appManager = ApplicationManager()
