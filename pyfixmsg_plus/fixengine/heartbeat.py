import asyncio
import logging
from pyfixmsg_plus.fixengine.testrequest import TestRequest

class Heartbeat:
    def __init__(self, send_message_callback, config_manager, heartbeat_interval, state_machine, fix_engine, timeout=5):
        """
        Initializes the Heartbeat class.

        Args:
            send_message_callback (Callable): Callback to send messages.
            config_manager (ConfigManager): Configuration manager for FIX settings.
            heartbeat_interval (int): Interval between heartbeats in seconds.
            state_machine (StateMachine): State machine for session state tracking.
            fix_engine (FixEngine): FIX engine instance.
            timeout (int, optional): Timeout for network operations in seconds. Defaults to 5 seconds.
        """
        self.send_message_callback = send_message_callback
        self.config_manager = config_manager
        self.heartbeat_interval = heartbeat_interval
        self.state_machine = state_machine
        self.fix_engine = fix_engine
        self.timeout = timeout  # Configurable timeout for network delays
        self.logger = logging.getLogger('Heartbeat')
        self.last_sent_time = None
        self.last_received_time = None
        self.test_request_id = 0
        self.running = False
        self.test_request = TestRequest(self.send_message_callback, self.config_manager)

    async def start(self):
        """
        Starts the heartbeat process.
        """
        self.running = True
        self.state_machine.on_event('logon')
        self.last_sent_time = self.last_received_time = asyncio.get_event_loop().time()
        self.logger.info(f"Heartbeat started with interval: {self.heartbeat_interval} seconds and timeout: {self.timeout} seconds.")
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.check_heartbeat()
            except asyncio.TimeoutError:
                self.logger.error(f"Heartbeat operation timed out after {self.timeout} seconds.")
                await self.initiate_corrective_action()
            except Exception as e:
                self.logger.error(f"Unexpected error in heartbeat loop: {e}")

    async def stop(self):
        """
        Stops the heartbeat process.
        """
        self.running = False
        self.state_machine.on_event('stop')
        self.logger.info("Heartbeat stopped.")

    async def check_heartbeat(self):
        """
        Checks the heartbeat and triggers actions if necessary.
        """
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_sent_time >= self.heartbeat_interval:
            await self.send_heartbeat()

        if current_time - self.last_received_time >= self.heartbeat_interval * 2:
            await self.send_test_request()

        if current_time - self.last_received_time >= self.heartbeat_interval * 3:
            self.logger.error("Connection lost. Initiating corrective action.")
            await self.initiate_corrective_action()

    async def send_heartbeat(self):
        """
        Sends a heartbeat message.
        """
        heartbeat_message = {
            '35': '0',  # Heartbeat
        }
        try:
            await asyncio.wait_for(self.send_message_callback(heartbeat_message), timeout=self.timeout)
            self.last_sent_time = asyncio.get_event_loop().time()
            self.logger.info("Sent Heartbeat")
        except asyncio.TimeoutError:
            self.logger.error(f"Sending heartbeat timed out after {self.timeout} seconds.")
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat: {e}")

    async def send_test_request(self):
        """
        Sends a test request message.
        """
        try:
            test_req_id = await asyncio.wait_for(self.test_request.send_test_request(), timeout=self.timeout)
            self.logger.info(f"Sent Test Request with TestReqID {test_req_id}")
        except asyncio.TimeoutError:
            self.logger.error(f"Sending test request timed out after {self.timeout} seconds.")
        except Exception as e:
            self.logger.error(f"Failed to send test request: {e}")

    async def receive_heartbeat(self, message):
        """
        Handles a received heartbeat message.

        Args:
            message (dict): The received heartbeat message.
        """
        self.last_received_time = asyncio.get_event_loop().time()
        self.logger.info("Received Heartbeat")
        self.logger.debug(f"Heartbeat message content: {message}")

    async def receive_test_request(self, message):
        """
        Handles a received test request message.

        Args:
            message (dict): The received test request message.
        """
        heartbeat_message = {
            '35': '0',  # Heartbeat
            '112': message.get('112')  # TestReqID from Test Request
        }
        try:
            await asyncio.wait_for(self.send_message_callback(heartbeat_message), timeout=self.timeout)
            self.logger.info("Responded to Test Request with Heartbeat")
        except asyncio.TimeoutError:
            self.logger.error(f"Responding to test request timed out after {self.timeout} seconds.")
        except Exception as e:
            self.logger.error(f"Failed to respond to test request: {e}")

    async def initiate_corrective_action(self):
        """
        Initiates corrective action when connection is lost.
        """
        self.running = False
        self.logger.error("Connection lost. Corrective action initiated.")
        self.state_machine.on_event('disconnect')
        try:
            await asyncio.wait_for(self.fix_engine.retry_connect(), timeout=self.timeout)
        except asyncio.TimeoutError:
            self.logger.error(f"Reconnection attempt timed out after {self.timeout} seconds.")
        except Exception as e:
            self.logger.error(f"Failed to reconnect: {e}")
