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

    async def send(self, message): # message here is already bytes (wire_message)
        """Send a message to the connected peer."""
        async with self.lock:
            self.writer.write(message) # Corrected: removed .encode()
            await self.writer.drain()
            # Be careful logging raw bytes if they can be very long or contain non-printable characters
            # For FIX, it's usually fine, but consider logging a summary or decoded string if issues arise.
            self.logger.info(f"Sent: {message.decode(errors='replace') if isinstance(message, bytes) else message}")


    async def receive(self, handler):
        """Receive and process messages from the connected peer."""
        while self.running:
            try:
                data = await self.reader.read(4096)
                if not data: # Connection closed by peer
                    self.logger.info("Connection closed by peer.")
                    self.running = False # Stop trying to receive
                    # Optionally, trigger a disconnect or state change event here
                    break
                if data:
                    # Assuming handler expects a decoded string
                    await handler(data.decode(errors='replace'))
            except asyncio.IncompleteReadError:
                self.logger.warning("Incomplete read, connection may have been closed prematurely.")
                self.running = False
                break
            except ConnectionResetError:
                self.logger.warning("Connection reset by peer.")
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Error receiving message: {e}")
                self.running = False # Stop on other errors too
                break
        if not self.running:
             # Perform any necessary cleanup if the loop exited due to self.running being false
             await self.disconnect()


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
        self.running = True # Mark as running once transport is set

    async def start_accepting(self, incoming_connection_handler):
        """Start accepting incoming connections."""
        # Note: self.lock from Network class might not be appropriate here if it's per-instance
        # and start_server is a class-level or global-like operation.
        # However, asyncio.start_server itself is an async operation.
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH) if self.use_tls else None
        if self.use_tls and ssl_context:
            # Add paths to your server certificate and private key
            # ssl_context.load_cert_chain(certfile='path/to/cert.pem', keyfile='path/to/key.pem')
            self.logger.info("TLS enabled for acceptor. Ensure certfile and keyfile are set if required by your SSL context.")

        self.server = await asyncio.start_server(
            incoming_connection_handler, # This handler will be called for each new client
            self.host,
            self.port,
            ssl=ssl_context
        )
        self.logger.info(f"Acceptor listening on {self.host}:{self.port} with TLS={self.use_tls}")
        async with self.server:
            await self.server.serve_forever()

    # handle_client and handle_message are specific to how FixEngine wants to use the Acceptor.
    # The FixEngine's incoming_connection_handler will likely call methods on the Acceptor instance
    # or directly use the reader/writer for a specific connection.
    # The original handle_client and handle_message might be better placed in FixEngine
    # or a dedicated connection handler class if an Acceptor instance is to manage multiple clients.

    # For clarity, the Acceptor's role is primarily to listen and pass new connections to a handler.
    # The Network base class methods (send, receive, disconnect) would then operate on a *specific*
    # connection's reader/writer, which should be set by the incoming_connection_handler.

    # If FixEngine creates a new Acceptor object per connection, then the current structure is okay,
    # but typically one Acceptor listens and dispatches.
    # Let's assume FixEngine's `handle_incoming_connection` will correctly manage the reader/writer
    # for the specific connection it's handling, possibly by calling `acceptor_instance.set_transport(reader, writer)`
    # and then `acceptor_instance.receive(engine_specific_handler)`.


    # This disconnect should apply to the listening server, not a specific client connection.
    async def stop_accepting(self):
        """Stop the server from accepting new connections and close existing ones."""
        self.logger.info("Stopping acceptor...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.logger.info("Acceptor server closed.")
        # Disconnecting individual client connections would be handled by FixEngine or connection handlers.
        # Call super().disconnect() if the acceptor itself holds a connection (not typical for a listener)
        # await super().disconnect() # This would disconnect the "acceptor's connection" if it had one.


class Initiator(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)

    # set_transport is not typically needed for an initiator using the base Network.connect method,
    # as connect already sets self.reader and self.writer.
    # If it were to be used, it would imply an already established connection passed to the initiator.

    async def connect_with_logon(self, logon_message_bytes): # Expecting logon_message to be bytes
        """Establish a connection and send a logon message."""
        await self.connect() # This sets up self.reader and self.writer
        self.logger.info("Sending logon message...")
        await self.send(logon_message_bytes) # self.send expects bytes

    async def reconnect(self, logon_message_bytes_callback, retry_interval=5, max_retries=3):
        """Attempt to reconnect to the server with retries and resend logon."""
        # logon_message_bytes_callback should be a function that returns the logon message bytes
        # This is because sequence numbers or timestamps might need to be fresh.
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Reconnect attempt {attempt + 1}/{max_retries}...")
                await self.connect() # Re-establish connection
                logon_bytes = await logon_message_bytes_callback() # Get fresh logon message
                await self.send(logon_bytes) # Send logon
                self.logger.info(f"Reconnected to {self.host}:{self.port} on attempt {attempt + 1} and resent logon.")
                # If successful, the receive loop should be started by the calling code (e.g., FixEngine)
                return True # Indicate success
            except Exception as e:
                self.logger.error(f"Reconnect attempt {attempt + 1} failed: {e}")
                await self.disconnect() # Ensure cleanup before sleeping
                if attempt + 1 < max_retries:
                    await asyncio.sleep(retry_interval)
                else:
                    self.logger.error("Max reconnect attempts reached. Giving up.")
                    return False # Indicate failure
        return False


    # handle_server_message is essentially a receive loop.
    # It might be better named receive_loop or similar, and called by FixEngine.
    async def start_receiving(self, message_handler_callback):
        """Continuously receive and process messages from the server."""
        # Ensure we are connected before starting to receive
        if not self.running or not self.writer or not self.reader:
            self.logger.error("Cannot start receiving: Not connected.")
            return

        await self.receive(message_handler_callback)
