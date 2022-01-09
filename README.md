# SocketSite

A Python-based WebSocket solution for efficient inter-process communication and data synchronization between multiple processes on localhost.

## Features

- Seamless communication between multiple Python processes
- Efficient data exchange and synchronization using WebSocket protocol
- Built-in process management and port allocation
- Thread-safe operations with proper error handling
- Support for both synchronous and asynchronous operations
- Automatic connection management and recovery

## Requirements

- Python 3.7+
- websockets 10.4
- threadpool 1.3.2

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SocketSite.git
cd SocketSite
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Example

```python
# Server process
from websocket_server import WebSocketServer

server = WebSocketServer(port=8765)
server.start()

# Client process
from websocket_client import WebSocketClient

client = WebSocketClient(port=8765)
client.connect()
client.send_message("Hello, Server!")
```

### Process Management

```python
from manager import ProcessManager

# Initialize the process manager
manager = ProcessManager()

# Add processes to manage
manager.add_process("process1", target_function, args=())
manager.start_all()
```

### Data Synchronization

```python
from mixer import DataMixer

# Initialize the data mixer
mixer = DataMixer()

# Register data handlers
@mixer.on_data("channel_name")
def handle_data(data):
    print(f"Received data: {data}")

# Start mixing data
mixer.start()
```

## Architecture

The project consists of several key components:

1. `websocket_server.py`: WebSocket server implementation
2. `websocket_client.py`: WebSocket client implementation
3. `mixer.py`: Data synchronization and mixing logic
4. `port.py`: Port management utilities
5. `manager.py`: Process management and coordination

## Best Practices

1. Always use proper error handling:
```python
try:
    client.connect()
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
```

2. Close connections properly:
```python
with WebSocketClient(port=8765) as client:
    client.send_message("Hello")
```

3. Use the process manager for coordinated process handling:
```python
manager = ProcessManager()
manager.add_process("worker", worker_function)
manager.start_all()
try:
    manager.wait_all()
finally:
    manager.stop_all()
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
