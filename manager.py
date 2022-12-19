import asyncio
import multiprocessing
from typing import Type

from websocket_server import AsyncServer
from websocket_client import AsyncClient
import threading
from port import is_open_port

SITE_HOST = "127.0.0.1"


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

if __name__ == "__main__":
    @appManager.register
    class MyApplication(SiteApplication):
        port = 8011
    appManager.run()
