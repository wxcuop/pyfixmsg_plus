import asyncio
import ssl
import logging

class Network:
    def __init__(self, host, port, use_tls=False):
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.reader = None
        self.writer = None
        self.running = False
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger('Network')
        self.logger.setLevel(logging.DEBUG)

    async def connect(self):
        """Establish a connection to the server."""
        async with self.lock:
            ssl_context = ssl.create_default_context() if self.use_tls else None
            transport, protocol = await asyncio.get_event_loop().create_connection(
                lambda: asyncio.StreamReaderProtocol(asyncio.StreamReader()),
                self.host,
                self.port,
                ssl=ssl_context,
            )
            self.reader = protocol._stream_reader
            self.writer = asyncio.StreamWriter(
                transport, protocol, self.reader, asyncio.get_event_loop()
            )
            self.running = True
            self.logger.info(f"Connected to {self.host}:{self.port} with TLS={self.use_tls}")

    async def disconnect(self):
        """Close the connection."""
        async with self.lock:
            self.running = False
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            self.logger.info("Disconnected")

    async def send(self, message):
        """Send a message to the connected peer."""
        async with self.lock:
            self.writer.write(message.encode())
            await self.writer.drain()
            self.logger.info(f"Sent: {message}")

    async def receive(self, handler):
        """Receive and process messages from the connected peer."""
        while self.running:
            try:
                data = await self.reader.read(4096)
                if data:
                    await handler(data.decode())
            except Exception as e:
                self.logger.error(f"Error receiving message: {e}")
                break

class Acceptor(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)
        self.server = None

    async def set_transport(self, reader, writer):
        """Set the transport layer for the client connection."""
        self.reader = reader
        self.writer = writer
        self.client_address = writer.get_extra_info('peername')
        self.logger.info(f"Transport set for client {self.client_address}")

    async def start_accepting(self, incoming_connection_handler):
        """Start accepting incoming connections."""
        async with self.lock:
            ssl_context = ssl.create_default_context() if self.use_tls else None
            self.server = await asyncio.start_server(
                incoming_connection_handler,
                self.host,
                self.port,
                ssl=ssl_context,
            )
            self.logger.info(f"Listening on {self.host}:{self.port}")
            async with self.server:
                await self.server.serve_forever()

    async def handle_client(self, reader, writer):
        """Handle an incoming client connection."""
        await self.set_transport(reader, writer)
        await self.receive(self.handle_message)

    async def handle_message(self, data):
        """Override this method to handle incoming messages."""
        self.logger.info(f"Received: {data}")

    async def disconnect(self):
        """Stop the server and disconnect all clients."""
        async with self.lock:
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            await super().disconnect()

class Initiator(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)

    async def set_transport(self, reader, writer):
        """Set the transport layer for the server connection."""
        self.reader = reader
        self.writer = writer
        self.logger.info("Transport set for server connection")

    async def connect_with_logon(self, logon_message):
        """Establish a connection and send a logon message."""
        await self.connect()
        self.logger.info("Sending logon message...")
        await self.send(logon_message)

    async def reconnect(self, retry_interval=5, max_retries=3):
        """Attempt to reconnect to the server with retries."""
        for attempt in range(max_retries):
            try:
                await self.connect()
                self.logger.info(f"Reconnected to {self.host}:{self.port} on attempt {attempt + 1}")
                return
            except Exception as e:
                self.logger.error(f"Reconnect attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(retry_interval)
        self.logger.error("Max reconnect attempts reached. Giving up.")

    async def handle_server_message(self, handler):
        """Process incoming messages from the server."""
        while self.running:
            try:
                data = await self.reader.read(4096)
                if data:
                    await handler(data.decode())
            except Exception as e:
                self.logger.error(f"Error receiving message: {e}")
                break
