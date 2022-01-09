"""
Data Mixer Implementation

This module provides a robust implementation for managing WebSocket-based
inter-process communication and data synchronization. It includes utilities
for port management, server/client implementations, and process management.
"""

import asyncio
import logging
import multiprocessing
import pickle
import socket
import threading
from typing import List, Tuple, Iterable, Union, Type, Optional, Set, Any
import threadpool
import websockets
from websockets.legacy import server
from websockets.exceptions import ConnectionClosed, WebSocketException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SITE_HOST = "127.0.0.1"
DEFAULT_PORT_MIN = 0
DEFAULT_PORT_MAX = 65535
DEFAULT_THREAD_TIMEOUT = 30.0


def is_open_port(host: str, port: int) -> Tuple[int, bool]:
    """
    Check if a TCP port is open.
    
    Args:
        host: The host address to check
        port: The port number to check
        
    Returns:
        Tuple of (port, is_open)
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            result = sock.connect_ex((host, port))
            return port, not bool(result)
    except Exception as e:
        logger.error(f"Error checking port {port}: {e}")
        return port, False


def get_not_open_ports(host: str, ports: List[int]) -> List[int]:
    """
    Get a list of ports that are not currently open.
    
    Args:
        host: The host address to check
        ports: List of port numbers to check
        
    Returns:
        List of ports that are not open
    """
    try:
        pool = threadpool.ThreadPool(min(len(ports), multiprocessing.cpu_count() * 2))
        responses = []
        
        requests = threadpool.makeRequests(
            is_open_port,
            [((host, port), {}) for port in ports],
            lambda request, response: responses.append(response[0]) if not response[1] else None
        )
        
        for req in requests:
            pool.putRequest(req)
            
        pool.wait()
        responses.sort()
        
        return responses
    except Exception as e:
        logger.error(f"Error getting not open ports: {e}")
        return []
    finally:
        if 'pool' in locals():
            pool.dismissWorkers(len(pool.workers))


def _exec_detect_port(host: str, port: int, stride: int, max_limit: int) -> Tuple[bool, int]:
    """
    Internal function to detect available ports.
    
    Args:
        host: The host address to check
        port: Starting port number
        stride: Port increment value
        max_limit: Maximum port number
        
    Returns:
        Tuple of (success, port_number)
    """
    try:
        while 0 <= port <= max_limit:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                if sock.connect_ex((host, port)):
                    return True, port
            port += stride
        return False, 0
    except Exception as e:
        logger.error(f"Error detecting port: {e}")
        return False, 0


def get_sample_open_ports(
    host: str,
    num: int,
    min_limit: int = DEFAULT_PORT_MIN,
    max_limit: int = DEFAULT_PORT_MAX
) -> List[int]:
    """
    Get a sample of available open ports.
    
    Args:
        host: The host address to check
        num: Number of ports needed
        min_limit: Minimum port number
        max_limit: Maximum port number
        
    Returns:
        List of available port numbers
        
    Raises:
        AssertionError: If port range is invalid or insufficient ports available
    """
    assert min_limit <= (min_limit + num - 1) <= max_limit, \
        f"Port range ({min_limit}~{max_limit}, total {num}) must be between {DEFAULT_PORT_MIN} and {DEFAULT_PORT_MAX}!"
        
    try:
        pool = threadpool.ThreadPool(min(num, multiprocessing.cpu_count() * 2))
        responses = []
        
        requests = threadpool.makeRequests(
            _exec_detect_port,
            [((host, min_limit + x, num, max_limit), {}) for x in range(num)],
            lambda request, response: responses.append(response[1]) if response[0] else None
        )
        
        for req in requests:
            pool.putRequest(req)
            
        pool.wait()
        responses.sort()
        
        if len(responses) < num:
            raise RuntimeError(f"Insufficient available ports ({num})! Found only {len(responses)} ports.")
            
        return responses
    except Exception as e:
        logger.error(f"Error getting sample open ports: {e}")
        raise
    finally:
        if 'pool' in locals():
            pool.dismissWorkers(len(pool.workers))


class AsyncServerClient:
    """
    WebSocket server client implementation.
    
    Handles individual client connections and message passing.
    """
    
    def __init__(self, websocket: server.WebSocketServerProtocol, parent: 'AsyncServer') -> None:
        """
        Initialize a new server client.
        
        Args:
            websocket: The WebSocket connection protocol
            parent: Reference to the parent server
        """
        self.websocket = websocket
        self.parent = parent
        self.is_alive = False
        self.client_id = id(self)
        logger.info(f"New server client connected: {self.client_id}")

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
            logger.error(f"Error in client {self.client_id} listener: {e}")
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

    async def send(self, message: Union[str, bytes]) -> bool:
        """
        Send a message to the client.
        
        Args:
            message: The message to send
            
        Returns:
            bool: True if message was sent successfully
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
            bool: True if object was sent successfully
        """
        try:
            return await self.send(pickle.dumps(obj))
        except Exception as e:
            logger.error(f"Error pickling object for client {self.client_id}: {e}")
            return False


class AsyncServer:
    """
    WebSocket server implementation.
    
    Manages multiple client connections and message broadcasting.
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
        await self.group_send(message)


class BaseProcessApplicationServer(multiprocessing.Process):
    """Base class for process-based application servers."""
    
    def __init__(self, port: int) -> None:
        """
        Initialize the process application server.
        
        Args:
            port: The port number to use
        """
        super().__init__()
        self.ws_thread: Optional[threading.Thread] = None
        self.server: Optional[AsyncServer] = None
        self.port = port
        logger.info(f"Initializing process application server on port {port}")

    def run_process(self) -> None:
        """Override this method to implement custom process logic."""
        pass

    def run(self) -> None:
        """Start the process and WebSocket server."""
        super().run()
        try:
            self.server = AsyncServer((SITE_HOST, self.port))
            self.ws_thread = threading.Thread(target=self.server.listen)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            self.run_process()
        except Exception as e:
            logger.error(f"Error in process application server: {e}")


class BaseAsyncApplicationClient(AsyncClient):
    """Base class for asynchronous application clients."""
    
    def __init__(self, port: int, loop: asyncio.AbstractEventLoop) -> None:
        """
        Initialize the async application client.
        
        Args:
            port: The port number to connect to
            loop: The event loop to use
        """
        super().__init__(addr=(SITE_HOST, port), loop=loop)
        self.listen()
        logger.info(f"Initialized async application client on port {port}")


class SiteApplication:
    """Site application manager."""
    
    port: int
    process_application = BaseProcessApplicationServer
    async_client = BaseAsyncApplicationClient

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Initialize the site application.
        
        Args:
            loop: The event loop to use
        """
        assert isinstance(self.port, int), "Port must be an integer"

        try:
            if is_open_port(SITE_HOST, self.port)[1]:
                self.app = self.process_application(self.port)
                self.app.start()
                logger.info(f"Started process application on port {self.port}")
            self.client = self.async_client(self.port, loop)
        except Exception as e:
            logger.error(f"Error initializing site application: {e}")
            raise


class ApplicationManager:
    """Manager for multiple site applications."""
    
    def __init__(self) -> None:
        """Initialize the application manager."""
        self.apps: List[SiteApplication] = []
        self.loop = asyncio.new_event_loop()
        logger.info("Initialized application manager")

    def register(self, exec_cls: Type[SiteApplication]) -> SiteApplication:
        """
        Register a new site application.
        
        Args:
            exec_cls: The site application class to register
            
        Returns:
            The initialized site application instance
        """
        try:
            app = exec_cls(self.loop)
            self.apps.append(app)
            logger.info(f"Registered application: {exec_cls.__name__}")
            return app
        except Exception as e:
            logger.error(f"Error registering application {exec_cls.__name__}: {e}")
            raise

    def run(self) -> None:
        """Start the application manager event loop."""
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Application manager shutting down...")
        except Exception as e:
            logger.error(f"Error in application manager: {e}")
        finally:
            self.loop.close()


# Global application manager instance
appManager = ApplicationManager()
