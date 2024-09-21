# llamafile Load Balancer Proxy

## Overview

This project implements a load balancer proxy for llamafile instances. It allows running multiple llamafile servers and distributing incoming requests across these instances. The proxy is built using Python and the aiohttp library, providing asynchronous handling of requests.

## Features

- Starts multiple llamafile instances based on commands in a configuration file
- Proxies incoming requests to available llamafile instances
- Basic load balancing using a hash-based distribution method
- Handles Server-Sent Events (SSE) for streaming responses
- Health checking of llamafile instances
- Detailed logging for request handling and server selection

## Prerequisites

- Python 3.11 or higher (tested with 3.11)
- aiohttp library
- Your favourite llamafile executable(s)

## Setup

1. Clone this repository to your local machine.
2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```
3. Create a file named `llamafile_commands.txt` in the same directory as the script. Each line should contain a command to start a llamafile instance, for example:
   ```
   /path/to/llamafile --server --nobrowser --host 0.0.0.0 --port 8080 --threads 4 --ctx-size 2048 --parallel 2 --alias gemma1
   /path/to/llamafile --server --nobrowser --host 0.0.0.0 --port 8081 --threads 4 --ctx-size 2048 --parallel 2 --alias gemma2
   ```

## Usage

Run the script using Python:

```
python load_balancer_proxy.py
```

The load balancer will start on `http://0.0.0.0:8088` by default.

## Configuration

- `COMMANDS_FILE`: The file containing llamafile startup commands (default: "llamafile_commands.txt")
- `OUTPUT_DIR`: Directory to store llamafile output logs (default: "llamafile_outputs")
- `PROXY_IP`: loopback address is set to 0.0.0.0 by default feel free to override it
- `PROXY_PORT`: port on which this proxy service will run on, default is set to 8088

## Load Balancing

The current implementation uses a simple hash-based load balancing method:

```python
target_port = instances[hash(str(request)) % len(instances)]
```

Note: This method may result in uneven distribution, especially for requests from the same client session. 

### Potential Improvement

A more even distribution can be achieved using a Round Robin balancer. An example implementation is provided in the code comments.

## Logging

The script uses Python's logging module to provide detailed logs about request handling, server selection, and any errors that occur.

## Health Checking

The proxy implements a basic health checking mechanism for the llamafile instances. The overall health status can be accessed at the `/health` endpoint.

## Limitations and Known Issues

- The current load balancing method may not provide perfectly even distribution across instances.
- There's no automatic recovery or restarting of failed llamafile instances.


## Contributing

Contributions to improve the load balancer are welcome. Please consider the following areas for enhancement:

1. Implementing a more sophisticated load balancing algorithm (e.g., Round Robin, Least Connections)
2. Implementing automatic recovery of failed llamafile instances
3. Enhancing the health checking mechanism
4. Adding configuration options for easier deployment in different environments and instead of hard coded values use config