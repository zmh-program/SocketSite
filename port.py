"""
TCP Port Management Module

This module provides utilities for detecting and managing TCP ports,
including checking port availability and finding open ports.
"""

import logging
import multiprocessing
import socket
from typing import List, Tuple, Optional
import threadpool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PORT_MIN = 0
DEFAULT_PORT_MAX = 65535
DEFAULT_TIMEOUT = 1.0
DEFAULT_THREAD_POOL_SIZE = multiprocessing.cpu_count() * 2


def is_open_port(host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> Tuple[int, bool]:
    """
    Check if a TCP port is open on the specified host.
    
    Args:
        host: The host address to check
        port: The port number to check
        timeout: Socket timeout in seconds
        
    Returns:
        Tuple of (port, is_open)
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return port, not bool(result)
    except Exception as e:
        logger.error(f"Error checking port {port} on {host}: {e}")
        return port, False


def get_not_open_ports(
    host: str,
    ports: List[int],
    thread_pool_size: Optional[int] = None
) -> List[int]:
    """
    Get a list of ports that are not currently open.
    
    Args:
        host: The host address to check
        ports: List of port numbers to check
        thread_pool_size: Size of the thread pool (defaults to CPU count * 2)
        
    Returns:
        List of ports that are not open
    """
    if not ports:
        logger.warning("Empty port list provided")
        return []

    pool_size = min(
        thread_pool_size or DEFAULT_THREAD_POOL_SIZE,
        len(ports)
    )
    
    try:
        pool = threadpool.ThreadPool(pool_size)
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
        
        logger.info(f"Found {len(responses)} closed ports out of {len(ports)} checked")
        return responses
        
    except Exception as e:
        logger.error(f"Error getting not open ports: {e}")
        return []
    finally:
        if 'pool' in locals():
            pool.dismissWorkers(len(pool.workers))


def _exec_detect_port(
    host: str,
    port: int,
    stride: int,
    max_limit: int,
    timeout: float = DEFAULT_TIMEOUT
) -> Tuple[bool, int]:
    """
    Internal function to detect available ports.
    
    Args:
        host: The host address to check
        port: Starting port number
        stride: Port increment value
        max_limit: Maximum port number
        timeout: Socket timeout in seconds
        
    Returns:
        Tuple of (success, port_number)
    """
    try:
        while 0 <= port <= max_limit:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
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
    max_limit: int = DEFAULT_PORT_MAX,
    thread_pool_size: Optional[int] = None
) -> List[int]:
    """
    Get a sample of available open ports.
    
    Args:
        host: The host address to check
        num: Number of ports needed
        min_limit: Minimum port number
        max_limit: Maximum port number
        thread_pool_size: Size of the thread pool (defaults to number of ports)
        
    Returns:
        List of available port numbers
        
    Raises:
        ValueError: If port range is invalid
        RuntimeError: If insufficient ports are available
    """
    if not (DEFAULT_PORT_MIN <= min_limit <= max_limit <= DEFAULT_PORT_MAX):
        raise ValueError(
            f"Port range ({min_limit}~{max_limit}) must be between "
            f"{DEFAULT_PORT_MIN} and {DEFAULT_PORT_MAX}"
        )
        
    if min_limit + num - 1 > max_limit:
        raise ValueError(
            f"Requested number of ports ({num}) exceeds available range "
            f"({min_limit}~{max_limit})"
        )
    
    pool_size = min(
        thread_pool_size or num,
        DEFAULT_THREAD_POOL_SIZE
    )
    
    try:
        pool = threadpool.ThreadPool(pool_size)
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
            raise RuntimeError(
                f"Insufficient available ports. Requested: {num}, "
                f"Found: {len(responses)}"
            )
            
        logger.info(f"Found {len(responses)} available ports")
        return responses
        
    except Exception as e:
        logger.error(f"Error getting sample open ports: {e}")
        raise
    finally:
        if 'pool' in locals():
            pool.dismissWorkers(len(pool.workers))


if __name__ == "__main__":
    try:
        ports = get_sample_open_ports(
            "127.0.0.1",
            100,
            min_limit=1,
            max_limit=100
        )
        print(f"Found available ports: {ports}")
    except Exception as e:
        logger.error(f"Error in main: {e}")
