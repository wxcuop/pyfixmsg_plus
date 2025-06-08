import asyncio
import logging
from pyfixmsg_plus.fixengine.testrequest import TestRequest

class Heartbeat:
    def __init__(self, send_message_callback, config_manager, heartbeat_interval, state_machine, fix_engine):
        self.send_message_callback = send_message_callback
        self.config_manager = config_manager
        self.heartbeat_interval = heartbeat_interval
        self.state_machine = state_machine
        self.fix_engine = fix_engine
        self.logger = logging.getLogger('Heartbeat')
        self.last_sent_time = None
        self.last_received_time = None
        self.test_request_id = 0
        self.running = False
        self.test_request = TestRequest(self.send_message_callback, self.config_manager)

    async def start(self):
        self.running = True
        self.state_machine.on_event('logon')
        self.last_sent_time = self.last_received_time = asyncio.get_event_loop().time()
        self.logger.info(f"Heartbeat started with interval: {self.heartbeat_interval} seconds.")
        while self.running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_heartbeat()

    async def stop(self):
        self.running = False
        self.state_machine.on_event('stop')
        self.logger.info("Heartbeat stopped.")

    async def check_heartbeat(self):
        current_time = asyncio.get_event_loop().time()
        if current_time - self.last_sent_time >= self.heartbeat_interval:
            await self.send_heartbeat()

        if current_time - self.last_received_time >= self.heartbeat_interval * 2:
            await self.send_test_request()

        if current_time - self.last_received_time >= self.heartbeat_interval * 3:
            self.logger.error("Connection lost. Initiating corrective action.")
            await self.initiate_corrective_action()

    async def send_heartbeat(self):
        heartbeat_message = {
            '35': '0',  # Heartbeat
        }
        await self.send_message_callback(heartbeat_message)
        self.last_sent_time = asyncio.get_event_loop().time()
        self.logger.info("Sent Heartbeat")

    async def send_test_request(self):
        test_req_id = await self.test_request.send_test_request()
        self.logger.info(f"Sent Test Request with TestReqID {test_req_id}")

    async def receive_heartbeat(self, message):
        self.last_received_time = asyncio.get_event_loop().time()
        self.logger.info("Received Heartbeat")

    async def receive_test_request(self, message):
        heartbeat_message = {
            '35': '0',  # Heartbeat
            '112': message.get('112')  # TestReqID from Test Request
        }
        await self.send_message_callback(heartbeat_message)
        self.logger.info("Responded to Test Request with Heartbeat")

    async def initiate_corrective_action(self):
        self.running = False
        self.logger.error("Connection lost. Corrective action initiated.")
        self.state_machine.on_event('disconnect')
        await self.fix_engine.retry_connect()
