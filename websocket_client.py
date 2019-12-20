from typing import *
import websockets
import asyncio


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


if __name__ == "__main__":
    _client = AsyncClient(("127.0.0.1", 8000))
    _client.listen()
    _client.loop.run_forever()
