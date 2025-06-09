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
        self.lock = asyncio.Lock() # Lock for critical sections like connect/disconnect/send
        self.logger = logging.getLogger(self.__class__.__name__) # Use class name for logger
        # self.logger.setLevel(logging.DEBUG) # Level should be set by application's logging config

    async def connect(self):
        """Establish a connection to the server."""
        async with self.lock:
            if self.running and self.writer: # Already connected
                self.logger.info(f"Already connected to {self.host}:{self.port}.")
                return

            self.logger.info(f"Attempting to connect to {self.host}:{self.port} with TLS={self.use_tls}...")
            ssl_context = ssl.create_default_context() if self.use_tls else None
            try:
                self.reader, self.writer = await asyncio.open_connection(
                    self.host,
                    self.port,
                    ssl=ssl_context
                )
                self.running = True
                self.logger.info(f"Successfully connected to {self.host}:{self.port}.")
            except ConnectionRefusedError:
                self.logger.error(f"Connection refused by {self.host}:{self.port}.")
                self.running = False
                self.reader = None
                self.writer = None
                raise # Re-raise to allow caller to handle
            except asyncio.TimeoutError:
                self.logger.error(f"Connection attempt to {self.host}:{self.port} timed out.")
                self.running = False
                self.reader = None
                self.writer = None
                raise
            except Exception as e:
                self.logger.error(f"Failed to connect to {self.host}:{self.port}: {e}", exc_info=True)
                self.running = False
                self.reader = None
                self.writer = None
                raise # Re-raise for other connection errors

    async def disconnect(self):
        """Close the connection."""
        async with self.lock:
            if not self.running and not self.writer: # Already disconnected or never connected
                self.logger.info("Disconnect called but not connected or already disconnected.")
                return

            self.running = False # Signal that we are no longer running/connected
            if self.writer:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                    self.logger.info("Connection writer closed.")
                except Exception as e:
                    self.logger.error(f"Error during writer close: {e}", exc_info=True)
                finally:
                    self.writer = None # Clear writer
            self.reader = None # Clear reader as well, as connection is gone
            self.logger.info(f"Disconnected from {self.host}:{self.port}.")


    async def send(self, message: bytes): # Ensure message is bytes
        """Send a message to the connected peer."""
        if not self.running or not self.writer:
            self.logger.error("Cannot send: Not connected or writer is not available.")
            # Consider raising an exception here if sending on a non-active connection is a critical error
            # For example: raise ConnectionError("Not connected")
            return

        async with self.lock: # Protect write and drain operations
            if not self.running or not self.writer: # Double check after acquiring lock
                self.logger.warning("Send aborted: Connection became unavailable after acquiring lock.")
                return
            try:
                self.writer.write(message)
                await self.writer.drain()
                # Log decoded message for readability, but be cautious with large messages or binary data
                self.logger.debug(f"Sent: {message.decode(errors='replace')}") # Changed to debug
            except ConnectionResetError:
                self.logger.error("Connection reset by peer during send. Marking as disconnected.")
                await self.disconnect() # Ensure state is updated
                raise # Re-raise so caller knows send failed
            except Exception as e:
                self.logger.error(f"Error sending message: {e}", exc_info=True)
                await self.disconnect() # Disconnect on other send errors too
                raise # Re-raise

    async def receive(self, handler):
        """Receive and process messages from the connected peer."""
        if not self.running: # Initial check before loop
            self.logger.warning("Receive loop called but not running.")
            return

        self.logger.info("Receive loop started.")
        try:
            while self.running:
                if self.reader is None:
                    self.logger.error("Reader is None. Cannot continue receiving. Marking as disconnected.")
                    # This state should ideally be prevented by proper connect/disconnect logic
                    await self.disconnect() # This will set self.running = False
                    break # Exit the loop

                try:
                    # Using readuntil(SOH) might be more FIX-appropriate if messages are framed by SOH,
                    # but generic read(4096) is also common for chunked reading.
                    # For FIX, you typically read until you have a complete message based on BodyLength (9).
                    # This simple read(4096) assumes the handler can deal with partial messages or reassemble them.
                    data = await self.reader.read(4096)
                except asyncio.IncompleteReadError: # Often means EOF or connection closed by peer
                    self.logger.warning("Incomplete read, connection closed by peer.")
                    await self.disconnect() # This will set self.running = False
                    break
                except ConnectionResetError:
                    self.logger.warning("Connection reset by peer during read.")
                    await self.disconnect() # This will set self.running = False
                    break
                except Exception as e: # Other read-related errors
                    self.logger.error(f"Error during self.reader.read: {e}", exc_info=True)
                    await self.disconnect() # This will set self.running = False
                    break

                if not data: # Connection closed by peer (EOF)
                    self.logger.info("Connection closed by peer (EOF received).")
                    await self.disconnect() # This will set self.running = False
                    break
                
                # If data is received, pass to handler
                # self.logger.debug(f"Received raw data chunk (first 100 bytes): {data[:100]}")
                try:
                    await handler(data) # Pass raw bytes to handler; handler decodes/parses
                except Exception as e_handler:
                    self.logger.error(f"Error in message handler: {e_handler}", exc_info=True)
                    # Decide if an error in the handler should stop the receive loop
                    # For now, we'll continue, but this might need more sophisticated error handling.

            # Loop exited, either self.running became false or a break occurred.
        except Exception as e_outer:
            # Catch-all for unexpected errors in the receive loop's structure itself
            self.logger.critical(f"Critical unexpected error in receive loop structure: {e_outer}", exc_info=True)
            if self.running: # If an error occurred but running is still somehow true
                await self.disconnect()
        finally:
            self.logger.info("Receive loop terminated.")
            # Ensure disconnect is called if loop terminates and we were supposed to be running
            # This is somewhat redundant if all paths inside the loop that set self.running=False also call disconnect.
            # However, it's a safeguard.
            if self.writer is not None or self.reader is not None: # If resources still appear to be held
                 if not await self.is_really_disconnected(): # Check if disconnect logic truly ran
                    self.logger.warning("Receive loop ended; ensuring final disconnect.")
                    await self.disconnect()


    async def is_really_disconnected(self):
        """Helper to check if resources are released."""
        return self.writer is None and self.reader is None and not self.running


class Acceptor(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)
        self.server = None
        self.client_handlers = {} # To manage individual client connection tasks

    async def set_transport_for_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        This method is intended to be called by the connection handler
        for a *new* Network object representing a single client connection,
        not on the Acceptor instance itself if it's just a listener.
        Alternatively, the Acceptor manages multiple client Network objects.

        For simplicity, if FixEngine creates a new Network-like object per client,
        that object would get its reader/writer set.
        If this Acceptor instance is meant to BE the network layer for ONE accepted client at a time,
        then this is fine.
        """
        async with self.lock: # Protect access to self.reader/writer
            self.reader = reader
            self.writer = writer
            self.client_address = writer.get_extra_info('peername')
            self.running = True # Mark this specific connection as running
            self.logger.info(f"Transport set for accepted client {self.client_address}. This Acceptor instance will now handle this client.")


    async def _handle_one_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, engine_message_handler):
        """
        Handles a single client connection.
        This would typically involve creating a new session/handler context in FixEngine.
        For this Network class, it means setting its own reader/writer to this client's
        and then starting its receive loop.
        """
        # This approach makes the Acceptor instance handle one client at a time after accepting.
        # A more advanced acceptor would spawn a new handler (and potentially new Network object) per client.
        self.logger.info(f"Accepted new connection from {writer.get_extra_info('peername')}.")
        await self.set_transport_for_client(reader, writer)
        
        # The engine_message_handler is what FixEngine provides to process incoming FIX messages
        # for this specific client connection.
        await self.receive(engine_message_handler)
        # When receive loop finishes (connection closed/error), this task for _handle_one_client ends.

    async def start_accepting(self, per_client_fix_engine_handler_coro_factory):
        """
        Start accepting incoming connections.
        per_client_fix_engine_handler_coro_factory: A coroutine function that takes (reader, writer)
                                                     and is called by FixEngine to set up a new session
                                                     and return the actual message processing callback.
        """
        ssl_context = None
        if self.use_tls:
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            # self.logger.info("TLS enabled. Configure certfile/keyfile for ssl_context if needed via FixEngine/Config.")
            # Example: ssl_context.load_cert_chain(certfile='path/server.crt', keyfile='path/server.key')


        async def client_connected_cb(reader, writer):
            # This callback is executed by asyncio.start_server for each new client.
            # FixEngine should provide the 'per_client_fix_engine_handler_coro_factory'
            # which will set up a session and provide the *actual* message handler for raw bytes.
            await per_client_fix_engine_handler_coro_factory(reader, writer)


        self.server = await asyncio.start_server(
            client_connected_cb, 
            self.host,
            self.port,
            ssl=ssl_context
        )
        self.logger.info(f"Acceptor listening on {self.host}:{self.port} with TLS={self.use_tls}")
        try:
            async with self.server:
                await self.server.serve_forever()
        except asyncio.CancelledError:
            self.logger.info("Acceptor server serve_forever task cancelled.")
        finally:
            self.logger.info("Acceptor server has stopped serving.")


    async def stop_accepting(self):
        self.logger.info("Stopping acceptor server...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.logger.info("Acceptor server closed.")
        # Note: This stops accepting NEW connections. Existing connections are managed by their tasks.
        # If this Acceptor instance was also handling a specific client (due to _handle_one_client model),
        # that client's connection should also be gracefully disconnected if desired.
        # However, the base `disconnect` is for an established connection, not the listening server.
        # If the acceptor itself was also a client (not typical), then:
        # await super().disconnect()


class Initiator(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)

    async def connect_and_logon(self, logon_message_bytes: bytes): # Renamed for clarity
        """Establish a connection and send a logon message."""
        await self.connect() # Base Network.connect() sets up self.reader/writer, self.running
        # No need to check self.running here as self.connect() would raise if failed
        self.logger.info("TCP Connected. Sending logon message...")
        await self.send(logon_message_bytes) # self.send expects bytes
        self.logger.info("Logon message sent.")

    async def start_main_receive_loop(self, fix_engine_message_handler):
        """
        Continuously receive and process messages from the server.
        fix_engine_message_handler: An async callback from FixEngine to handle raw incoming bytes.
        """
        if not self.running or not self.writer or not self.reader:
            self.logger.error("Cannot start receiving: Not connected or streams not available.")
            return False # Indicate failure to start

        await self.receive(fix_engine_message_handler)
        # self.receive will call self.disconnect() internally if the loop terminates.
        return True # Indicates loop started (though it might have terminated immediately)

    # Reconnect logic might be better placed in FixEngine to coordinate state,
    # but can be a utility here.
    async def attempt_reconnect_and_logon(self, logon_callback, retry_interval=5, max_retries=3):
        """
        Attempt to reconnect to the server with retries and resend logon.
        logon_callback: An async function that returns the (fresh) logon message bytes.
        """
        for attempt in range(max_retries):
            self.logger.info(f"Reconnect attempt {attempt + 1}/{max_retries}...")
            try:
                # Ensure we are fully disconnected before attempting to connect again
                if self.running or self.writer or self.reader:
                    await self.disconnect() 
                
                await self.connect() # Establishes connection, sets self.running
                
                logon_bytes = await logon_callback() # Get fresh logon message
                await self.send(logon_bytes) # Send logon
                
                self.logger.info(f"Reconnected to {self.host}:{self.port} and resent logon on attempt {attempt + 1}.")
                return True # Indicate success
            except ConnectionRefusedError:
                self.logger.warning(f"Reconnect attempt {attempt + 1} failed: Connection refused.")
            except Exception as e:
                self.logger.error(f"Reconnect attempt {attempt + 1} failed: {e}", exc_info=True)
            
            # If connect or send failed, disconnect should have been called internally by them if they manage state,
            # but an explicit disconnect here ensures cleanup before retry.
            if self.running or self.writer or self.reader: # If still somehow connected
                 await self.disconnect()

            if attempt + 1 < max_retries:
                self.logger.info(f"Waiting {retry_interval}s before next reconnect attempt.")
                await asyncio.sleep(retry_interval)
            else:
                self.logger.error("Max reconnect attempts reached. Giving up.")
                return False
        return False # Should not be reached if max_retries > 0
