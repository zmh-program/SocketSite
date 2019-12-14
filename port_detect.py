import socket
from typing import *
import threadpool


def is_open_port(addr) -> bool:
    return not not socket.socket().connect_ex(addr)


def _exec_detect_port(host: str, port: int, stride: int, max_limit: int) -> Tuple[bool, int]:
    while 0 <= port <= max_limit:
        if socket.socket().connect_ex((host, port)):
            return True, port
        port += stride
        return False, 0


def get_open_ports(host: str, num: int, min_limit: int = 0, max_limit: int = 65535) -> List[Tuple[int]]:
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


if __name__ == "__main__":
    ns = get_open_ports("127.0.0.1", 100, min_limit=1, max_limit=100)
    print(ns)
