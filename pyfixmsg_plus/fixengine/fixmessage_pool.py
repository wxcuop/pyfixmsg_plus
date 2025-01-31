from pyfixmsg.fixmessage import FixMessage

class FixMessagePool:
    def __init__(self, size):
        self.pool = [FixMessage() for _ in range(size)]
        self.available = self.pool[:]

    def get_message(self):
        if not self.available:
            return FixMessage()  # Create a new FixMessage if the pool is exhausted
        return self.available.pop()

    def return_message(self, message):
        message.clear()  # Clear or reset the message fields
        self.available.append(message)
