import asyncio
import multiprocessing
from typing import Type

from websocket_server import AsyncServer
from websocket_client import AsyncClient
import threading
from port import is_open_port

SITE_HOST = "127.0.0.1"


class BaseProcessApplicationServer(AsyncServer, multiprocessing.Process):
    def __init__(self, port: int):
        self.ws_thread = threading.Thread(target=self.listen)
        super().__init__(addr=(SITE_HOST, port))

    def run_process(self):
        pass

    def run(self):
        super().run()
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


appManager = ApplicationManager()

if __name__ == "__main__":
    @appManager.register
    class MyApplication(SiteApplication):
        port = 8011
