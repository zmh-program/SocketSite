"""
WebSocket Server Implementation

This module provides a robust WebSocket server implementation with support for
multiple client connections, message broadcasting, and pickle serialization.
"""

import asyncio
import logging
import pickle
from typing import List, Tuple, Iterable, Optional, Set, Any
import websockets
from websockets.legacy import server
from websockets.exceptions import ConnectionClosed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AsyncServerClient:
    """
    Represents a connected WebSocket client.
    
    Handles individual client connections, message sending/receiving,
    and pickle serialization/deserialization.
    """
    
    def __init__(self, websocket: server.WebSocketServerProtocol, parent: 'AsyncServer') -> None:
        """
        Initialize a new client connection.
        
        Args:
            websocket: The WebSocket connection protocol
            parent: Reference to the parent server instance
        """
        self.websocket = websocket
        self.parent = parent
        self.is_alive = False
        self.client_id = id(self)
        logger.info(f"New client connected: {self.client_id} from {websocket.remote_address}")

    async def listen(self) -> None:
        """Listen for incoming messages from the client."""
        self.is_alive = True
        try:
            async for message in self.websocket:
                try:
                    await self.parent.receive_from_websocket(self, message)
                except Exception as e:
                    logger.error(f"Error processing message from client {self.client_id}: {e}")
        except ConnectionClosed:
            logger.info(f"Client {self.client_id} connection closed")
        except Exception as e:
            logger.error(f"Unexpected error in client {self.client_id} listener: {e}")
        finally:
            self.is_alive = False
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up resources when the client disconnects."""
        try:
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing websocket for client {self.client_id}: {e}")

    @staticmethod
    def recv_pickle(pickle_data: bytes) -> Any:
        """
        Deserialize pickle data.
        
        Args:
            pickle_data: The pickled data to deserialize
            
        Returns:
            The deserialized object
        """
        try:
            return pickle.loads(pickle_data)
        except Exception as e:
            logger.error(f"Error deserializing pickle data: {e}")
            raise

    async def send(self, message: Any) -> bool:
        """
        Send a message to the client.
        
        Args:
            message: The message to send
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.is_alive:
            return False
            
        try:
            await self.websocket.send(message)
            return True
        except Exception as e:
            logger.error(f"Error sending message to client {self.client_id}: {e}")
            self.is_alive = False
            return False

    async def send_pickle(self, obj: Any) -> bool:
        """
        Serialize and send an object to the client.
        
        Args:
            obj: The object to serialize and send
            
        Returns:
            bool: True if object was sent successfully, False otherwise
        """
        try:
            return await self.send(pickle.dumps(obj))
        except Exception as e:
            logger.error(f"Error pickling object for client {self.client_id}: {e}")
            return False


class AsyncServer:
    """
    WebSocket server implementation supporting multiple client connections.
    
    Features:
    - Multiple client support
    - Host validation
    - Message broadcasting
    - Automatic connection management
    """
    
    client_type = AsyncServerClient

    def __init__(self, addr: Tuple[str, int], allow_hosts: Optional[List[str]] = None) -> None:
        """
        Initialize the WebSocket server.
        
        Args:
            addr: Tuple of (host, port)
            allow_hosts: List of allowed host addresses
        """
        self.addr = addr
        self.host, self.port = addr
        self.loop = asyncio.new_event_loop()
        self.clients: List[AsyncServerClient] = []
        self.is_alive = False
        self.allow_hosts: Set[str] = set(allow_hosts or [self.host, "localhost", "127.0.0.1"])
        logger.info(f"Initializing WebSocket server on {self.host}:{self.port}")

    @property
    def alive_clients(self) -> Iterable[AsyncServerClient]:
        """Get an iterator of currently connected clients."""
        return (client for client in self.clients if client.is_alive)

    def __iter__(self) -> Iterable[AsyncServerClient]:
        """Iterate over all clients."""
        return iter(self.clients)

    def __del__(self) -> None:
        """Cleanup when the server is destroyed."""
        self.clients = []

    async def add_client(self, websocket: server.WebSocketServerProtocol) -> None:
        """
        Add a new client connection.
        
        Args:
            websocket: The WebSocket connection protocol
        """
        host = websocket.remote_address[0]
        if host in self.allow_hosts:
            client = self.client_type(websocket, self)
            self.clients.append(client)
            logger.info(f"Added new client from {host}")
            await client.listen()
        else:
            logger.warning(f"Rejected connection from unauthorized host: {host}")
            await websocket.close()

    async def _listen(self) -> None:
        """Internal method to start the WebSocket server."""
        self.is_alive = True
        try:
            async with websockets.serve(self.add_client, self.host, self.port, loop=self.loop):
                logger.info(f"WebSocket server is running on ws://{self.host}:{self.port}")
                await asyncio.Future()  # run forever
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.is_alive = False

    def listen(self) -> None:
        """Start the WebSocket server."""
        try:
            self.loop.run_until_complete(self._listen())
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.loop.close()

    async def group_send(self, message: Any) -> Tuple[AsyncServerClient, ...]:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
            
        Returns:
            Tuple of clients that were removed due to failed sending
        """
        removed_clients = []
        for client in self.clients:
            if not await client.send(message):
                removed_clients.append(client)
                
        for client in removed_clients:
            self.clients.remove(client)
            logger.info(f"Removed disconnected client: {client.client_id}")
            
        return tuple(removed_clients)

    async def receive_from_websocket(self, client: AsyncServerClient, message: Any) -> None:
        """
        Handle incoming messages from clients.
        
        Args:
            client: The client that sent the message
            message: The received message
            
        Override this method to implement custom message handling.
        """
        # Default implementation: echo the message back to all clients
        await self.group_send(message)


if __name__ == "__main__":
    server = AsyncServer(("127.0.0.1", 8000))
    try:
        server.listen()
    except Exception as e:
        logger.error(f"Fatal server error: {e}")
