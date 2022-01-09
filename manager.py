"""
Application Manager Module

This module provides a framework for managing WebSocket-based applications,
including process-based servers and asynchronous clients.
"""

import asyncio
import logging
import multiprocessing
import threading
from typing import Type, List, Optional, Any

from websocket_server import AsyncServer
from websocket_client import AsyncClient
from port import is_open_port

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
SITE_HOST = "127.0.0.1"
DEFAULT_SHUTDOWN_TIMEOUT = 5.0


class BaseProcessApplicationServer(multiprocessing.Process):
    """
    Base class for process-based application servers.
    
    This class manages a WebSocket server in a separate process,
    allowing for true parallel execution of server tasks.
    """
    
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
        self._shutdown_event = threading.Event()
        logger.info(f"Initializing process application server on port {port}")

    def run_process(self) -> None:
        """
        Override this method to implement custom process logic.
        
        This method will be called after the WebSocket server is started.
        """
        pass

    def run(self) -> None:
        """Start the process and WebSocket server."""
        super().run()
        try:
            self.server = AsyncServer((SITE_HOST, self.port))
            self.ws_thread = threading.Thread(target=self.server.listen)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            logger.info(f"Started WebSocket server thread on port {self.port}")
            self.run_process()
            
            # Wait for shutdown signal
            self._shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error in process application server: {e}")
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources when shutting down."""
        try:
            if self.server and self.server.is_alive:
                self.server.loop.stop()
                self.server.loop.close()
            logger.info(f"Cleaned up process application server on port {self.port}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def shutdown(self, timeout: float = DEFAULT_SHUTDOWN_TIMEOUT) -> None:
        """
        Gracefully shut down the server.
        
        Args:
            timeout: Maximum time to wait for shutdown in seconds
        """
        self._shutdown_event.set()
        self.join(timeout)
        if self.is_alive():
            logger.warning(f"Server on port {self.port} did not shut down gracefully")
            self.terminate()


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
        try:
            self.listen()
            logger.info(f"Started async client on port {port}")
        except Exception as e:
            logger.error(f"Error initializing async client: {e}")
            raise


class SiteApplication:
    """
    Site application that manages both server and client components.
    
    This class should be subclassed to implement specific application behavior.
    The subclass must define:
    - port: The port number to use
    - process_application: The server process class (optional)
    - async_client: The client class (optional)
    """
    
    port: int
    process_application = BaseProcessApplicationServer
    async_client = BaseAsyncApplicationClient

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Initialize the site application.
        
        Args:
            loop: The event loop to use
        """
        if not isinstance(self.port, int):
            raise TypeError("Port must be an integer")

        self.loop = loop
        self.app: Optional[BaseProcessApplicationServer] = None
        self.client: Optional[BaseAsyncApplicationClient] = None
        
        try:
            # Check if port is available
            if is_open_port(SITE_HOST, self.port)[1]:
                self.app = self.process_application(self.port)
                self.app.start()
                logger.info(f"Started process application on port {self.port}")
            else:
                logger.warning(f"Port {self.port} is already in use")
                
            self.client = self.async_client(self.port, loop)
            
        except Exception as e:
            logger.error(f"Error initializing site application: {e}")
            self.cleanup()
            raise

    def cleanup(self) -> None:
        """Clean up application resources."""
        try:
            if self.app:
                self.app.shutdown()
            if self.client:
                self.loop.run_until_complete(self.client.close())
            logger.info(f"Cleaned up site application on port {self.port}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


class ApplicationManager:
    """
    Manager for multiple site applications.
    
    This class handles the lifecycle of multiple site applications,
    including initialization, registration, and cleanup.
    """
    
    def __init__(self) -> None:
        """Initialize the application manager."""
        self.apps: List[SiteApplication] = []
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        logger.info("Initialized application manager")

    def register(self, exec_cls: Type[SiteApplication]) -> SiteApplication:
        """
        Register a new site application.
        
        Args:
            exec_cls: The site application class to register
            
        Returns:
            The initialized site application instance
            
        Raises:
            ValueError: If the application class is invalid
        """
        if not issubclass(exec_cls, SiteApplication):
            raise ValueError("exec_cls must be a subclass of SiteApplication")
            
        try:
            app = exec_cls(self.loop)
            self.apps.append(app)
            logger.info(f"Registered application: {exec_cls.__name__}")
            return app
        except Exception as e:
            logger.error(f"Error registering application {exec_cls.__name__}: {e}")
            raise

    def cleanup(self) -> None:
        """Clean up all registered applications."""
        for app in self.apps:
            try:
                app.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up application: {e}")

    def run(self) -> None:
        """Start the application manager event loop."""
        try:
            logger.info("Starting application manager")
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Application manager shutting down...")
        except Exception as e:
            logger.error(f"Error in application manager: {e}")
        finally:
            self.cleanup()
            self.loop.stop()
            self.loop.close()


# Global application manager instance
appManager = ApplicationManager()


if __name__ == "__main__":
    try:
        # Example application
        @appManager.register
        class MyApplication(SiteApplication):
            port = 8011
            
            def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
                super().__init__(loop)
                logger.info("Initialized MyApplication")
                
        appManager.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
