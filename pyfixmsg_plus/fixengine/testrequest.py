from datetime import datetime
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory

class TestRequest:
    def __init__(self, send_message, config_manager):
        self.send_message = send_message
        self.config_manager = config_manager

    async def send_test_request(self):
        test_req_id = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")
        message = FixMessageFactory.create_message('1')
        message[49] = self.config_manager.get('FIX', 'sender', 'SERVER')
        message[56] = self.config_manager.get('FIX', 'target', 'CLIENT')
        message[112] = test_req_id  # TestReqID
        await self.send_message(message)
        return test_req_id

# Example usage
if __name__ == "__main__":
    import asyncio

    async def send_message(message):
        print(f"Sending message: {message}")

    config_manager = None  # Replace with actual config manager
    test_request = TestRequest(send_message, config_manager)
    asyncio.run(test_request.send_test_request())
