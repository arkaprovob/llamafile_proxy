import asyncio
import aiohttp
from aiohttp import web, ClientTimeout
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# File containing the commands to execute
COMMANDS_FILE = "llamafile_commands.txt"
# Directory to store output files
OUTPUT_DIR = "llamafile_outputs"

PROXY_IP = "0.0.0.0"
PROXY_PORT = 8088

# List to store the ports of running instances
instances = []


async def execute_command(command, port):
    output_file = os.path.join(OUTPUT_DIR, f"llamafile_output_{port}.log")
    with open(output_file, 'w') as f:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=f,
            stderr=asyncio.subprocess.STDOUT
        )
    return process


async def start_instances():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(COMMANDS_FILE, 'r') as file:
        commands = file.readlines()

    for command in commands:
        command = command.strip()
        if command:
            port = command.split('--port')[1].split()[0].strip()
            instances.append(int(port))
            await execute_command(command, port)
        logger.info(f"ports are {instances}")
    logger.info(f"Started {len(instances)} instances.")


async def health_check(port):
    url = f"http://localhost:{port}/health"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["status"] == "ok"
        except Exception as e:
            logger.error(f"Health check failed for port {port}: {str(e)}")
    return False


async def get_overall_health():
    health_statuses = await asyncio.gather(*[health_check(port) for port in instances])
    healthy_count = sum(health_statuses)
    total_count = len(instances)
    health_percentage = (healthy_count / total_count) * 100 if total_count > 0 else 0

    return {
        "status": "ok" if health_percentage == 100 else "degraded",
        "healthy_instances": healthy_count,
        "total_instances": total_count,
        "health_percentage": health_percentage
    }


async def stream_sse(request, target_url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(target_url, headers=request.headers, data=await request.read()) as response:
                streaming_response = web.StreamResponse(
                    status=response.status,
                    headers=response.headers
                )
                await streaming_response.prepare(request)

                async for chunk in response.content.iter_any():
                    await streaming_response.write(chunk)
                    await streaming_response.drain()

                return streaming_response
        except Exception as e:
            logger.error(f"SSE streaming failed: {str(e)}")
            return web.Response(status=503, text=f"Service Unavailable: {str(e)}")


async def proxy_handler(request):
    # NOTE: Current load balancing method
    # This method uses a hash of the request object to select a server instance.
    # While simple, it has limitations:
    # 1. Requests from the same client (e.g., browser session) often get routed to the same server.
    # 2. Distribution may not be even, especially with a small number of clients.
    #
    # Suggested improvement: Implement a Round Robin Balancer for better distribution.
    # Example implementation:
    #
    # class RoundRobinBalancer:
    #     def __init__(self, instances):
    #         self.instances = instances
    #         self.current = 0
    #
    #     def get_next(self):
    #         instance = self.instances[self.current]
    #         self.current = (self.current + 1) % len(self.instances)
    #         return instance
    #
    # balancer = RoundRobinBalancer(instances)
    #
    # Then replace the following line with:
    # target_port = balancer.get_next()
    #
    # This ensures each request is sent to the next server in the list,
    # providing a more even distribution of load across instances.

    request_id = id(request)  # Generate a unique ID for this request
    target_port = instances[hash(str(request)) % len(instances)]
    target_url = f"http://localhost:{target_port}{request.path_qs}"

    logger.info(f"Request ID: {request_id}")
    logger.info(f"Selected server port: {target_port}")
    logger.info(f"Received request for path: {request.path_qs}")
    logger.info(f"Proxying request to: {target_url}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request headers: {request.headers}")

    async with aiohttp.ClientSession() as session:
        try:
            body = await request.read()
            logger.info(f"Request body: {body.decode('utf-8')}")

            async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=request.headers,
                    data=body,
                    timeout=ClientTimeout(total=None)  # No timeout for SSE
            ) as response:
                logger.info(f"Request ID: {request_id} - Received response from target with status: {response.status}")
                logger.info(f"Request ID: {request_id} - Response headers: {response.headers}")

                if response.headers.get('Content-Type', '').startswith('text/event-stream'):
                    logger.info(f"Request ID: {request_id} - Streaming SSE response")
                    return await stream_sse(request, target_url)
                else:
                    logger.info(f"Request ID: {request_id} - Returning regular response")
                    return web.Response(
                        status=response.status,
                        headers=response.headers,
                        body=await response.read()
                    )
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Proxy request failed: {str(e)}")
            return web.Response(status=503, text=f"Service Unavailable: {str(e)}")


async def health_handler(request):
    health_status = await get_overall_health()
    return web.json_response(health_status)


async def main():
    await start_instances()

    app = web.Application()
    app.router.add_route('*', '/health', health_handler)
    app.router.add_route('*', '/{path:.*}', proxy_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=PROXY_IP, port=PROXY_PORT)
    await site.start()

    logger.info(f"Load balancer proxy started on http://{PROXY_IP}:{PROXY_PORT}")

    try:
        await asyncio.Future()  # Run forever
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
