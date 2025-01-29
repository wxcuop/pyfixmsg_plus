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
        async with self.lock:
            if self.use_tls:
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port, ssl=ssl.create_default_context())
            else:
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            self.running = True
            self.logger.info(f"Connected to {self.host}:{self.port} with TLS={self.use_tls}")

    async def disconnect(self):
        async with self.lock:
            self.running = False
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            self.logger.info("Disconnected")

    async def send(self, message):
        async with self.lock:
            self.writer.write(message)
            await self.writer.drain()
            self.logger.info(f"Sent: {message}")

    async def receive(self, handler):
        while self.running:
            data = await self.reader.read(4096)
            if data:
                await handler(data)

class Acceptor(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)
        self.server = None

    async def accept(self):
        async with self.lock:
            self.server = await asyncio.start_server(self.handle_client, self.host, self.port, ssl=ssl.create_default_context() if self.use_tls else None)
            self.logger.info(f"Listening on {self.host}:{self.port}")

    async def handle_client(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.client_address = writer.get_extra_info('peername')
        self.logger.info(f"Accepted connection from {self.client_address}")
        await self.receive(self.handle_message)

    async def handle_message(self, data):
        """Override this method to handle messages"""
        pass

    async def disconnect(self):
        async with self.lock:
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            await super().disconnect()

class Initiator(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)
