from pyfixmsg.fixmessage import FixMessage

class FixMessagePool:
    def __init__(self, size=20, codec=None):
        self.pool = [FixMessage(codec=codec) for _ in range(size)]
        self.codec = codec

    def get_message(self):
        if not self.pool:
            return FixMessage(codec=self.codec)
        return self.pool.pop()

    def return_message(self, message):
        self.pool.append(message)

# Usage example
# pool = FixMessagePool(size=20, codec=your_codec)
