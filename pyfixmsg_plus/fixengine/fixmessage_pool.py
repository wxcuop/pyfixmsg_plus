from pyfixmsg.fixmessage import FixMessage
import datetime

class FixMessagePool:
    def __init__(self, size=20, codec=None):
        self.pool = [FixMessage(codec=codec) for _ in range(size)]
        self.codec = codec

    def get_message(self):
        if not self.pool:
            message = FixMessage(codec=self.codec)
        else:
            message = self.pool.pop()
        message.time = datetime.datetime.utcnow()  # Update the time
        return message

    def return_message(self, message):
        self.pool.append(message)

# Usage example
# pool = FixMessagePool(size=20, codec=your_codec)
