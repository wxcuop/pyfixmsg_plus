import asyncio
import logging

class Heartbeat:
    def __init__(self, send_message_callback, config_manager, heartbeat_interval, state_machine):
        self.send_message_callback = send_message_callback
        self.heartbeat_interval = heartbeat_interval
        self.state_machine = state_machine  # Add state machine
        self.logger = logging.getLogger('Heartbeat')
        self.last_sent_time = None
        self.last_received_time = None
        self.test_request_id = 0
        self.running = False

    async def start(self):
        self.running = True
        self.state_machine.on_event('logon')  # Set state to ACTIVE
        self.last_sent_time = self.last_received_time = asyncio.get_event_loop().time()
        while self.running:
            await asyncio.sleep(self.heartbeat_interval)
            await self.check_heartbeat()

    async def stop(self):
        self.running = False

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
        self.test_request_id += 1
        test_request_message = {
            '35': '1',  # Test Request
            '112': str(self.test_request_id)  # TestReqID
        }
        await self.send_message_callback(test_request_message)
        self.logger.info("Sent Test Request")

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
        # Implement corrective action such as reconnecting or alerting the user

# Example usage
if __name__ == "__main__":
    async def send_message(message):
        print(f"Sending message: {message}")

    config_manager = None  # Replace with actual config manager
    heartbeat = Heartbeat(send_message, config_manager, 30)
    asyncio.run(heartbeat.start())
