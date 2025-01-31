from datetime import datetime
from fixmessage_factory import FixMessageFactory

class TestRequest:
    def __init__(self, send_message, config_manager):
        self.send_message = send_message
        self.config_manager = config_manager
        self.test_request_id = 0

    async def send_test_request(self):
        self.test_request_id += 1
        message = FixMessageFactory.create_message('1')
        message[49] = self.config_manager.get('FIX', 'sender', 'SERVER')
        message[56] = self.config_manager.get('FIX', 'target', 'CLIENT')
        message[112] = str(self.test_request_id)  # TestReqID
        await self.send_message(message)

# Example usage
if __name__ == "__main__":
    async def send_message(message):
        print(f"Sending message: {message}")

    config_manager = None  # Replace with actual config manager
    test_request = TestRequest(send_message, config_manager)
    asyncio.run(test_request.send_test_request())
