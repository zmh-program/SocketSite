"""
WebSocket Client Implementation

This module provides a robust WebSocket client implementation with support for
asynchronous communication, automatic reconnection, and message handling.
"""

import asyncio
import logging
from typing import Tuple, Union, Optional, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AsyncClient:
    """
    Asynchronous WebSocket client implementation.
    
    Features:
    - Asynchronous message sending/receiving
    - Automatic reconnection
    - Customizable message handling
    - Connection state management
    """

    def __init__(
        self, 
        addr: Tuple[str, int],
        loop: Optional[asyncio.AbstractEventLoop] = None,
        reconnect_interval: float = 5.0,
        max_retries: int = 5
    ) -> None:
        """
        Initialize the WebSocket client.
        
        Args:
            addr: Tuple of (host, port)
            loop: Optional event loop to use
            reconnect_interval: Time in seconds between reconnection attempts
            max_retries: Maximum number of reconnection attempts (-1 for infinite)
        """
        self.host, self.port = addr
        self.addr = addr
        self.loop = loop or asyncio.new_event_loop()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.reconnect_interval = reconnect_interval
        self.max_retries = max_retries
        self._retry_count = 0
        logger.info(f"Initializing WebSocket client for {self.url}")

    async def _connect(self) -> bool:
        """
        Establish connection to the WebSocket server.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            self.websocket = await websockets.connect(
                self.url,
                loop=self.loop,
                ping_interval=20,
                ping_timeout=10
            )
            self.is_connected = True
            self._retry_count = 0
            logger.info(f"Connected to WebSocket server at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def _listen(self) -> None:
        """Internal method to listen for incoming messages."""
        while True:
            try:
                if not self.is_connected:
                    if self.max_retries != -1 and self._retry_count >= self.max_retries:
                        logger.error("Max reconnection attempts reached")
                        break
                    
                    self._retry_count += 1
                    logger.info(f"Attempting to reconnect (attempt {self._retry_count})")
                    if not await self._connect():
                        await asyncio.sleep(self.reconnect_interval)
                        continue

                async for message in self.websocket:
                    try:
                        await self.receive_event(message)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

            except ConnectionClosed:
                logger.warning("Connection closed by server")
                self.is_connected = False
            except Exception as e:
                logger.error(f"Unexpected error in listener: {e}")
                self.is_connected = False
                await asyncio.sleep(self.reconnect_interval)

    def listen(self) -> asyncio.Future:
        """
        Start listening for incoming messages.
        
        Returns:
            asyncio.Future: The listening task
        """
        return asyncio.run_coroutine_threadsafe(self._listen(), self.loop)

    @property
    def url(self) -> str:
        """Get the WebSocket server URL."""
        return f"ws://{self.host}:{self.port}/"

    async def receive_event(self, message: Union[str, bytes]) -> None:
        """
        Handle incoming messages from the server.
        
        Args:
            message: The received message
            
        Override this method to implement custom message handling.
        """
        logger.debug(f"Received message: {message}")

    async def send(self, message: Union[str, bytes]) -> bool:
        """
        Send a message to the server.
        
        Args:
            message: The message to send
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.is_connected or not self.websocket:
            logger.error("Cannot send message: Not connected to server")
            return False

        try:
            await self.websocket.send(message)
            return True
        except WebSocketException as e:
            logger.error(f"Error sending message: {e}")
            self.is_connected = False
            return False

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
        self.is_connected = False

    def __enter__(self) -> 'AsyncClient':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        if self.websocket:
            self.loop.run_until_complete(self.close())
        self.loop.stop()
        self.loop.close()


if __name__ == "__main__":
    client = AsyncClient(("127.0.0.1", 8000))
    try:
        client.listen()
        client.loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Client shutting down...")
    finally:
        client.loop.run_until_complete(client.close())
        client.loop.close()
