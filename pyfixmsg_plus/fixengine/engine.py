import socket
import threading
import logging
from pyfixmsg.fixmessage import FixMessage
from pyfixmsg.codecs.stringfix import Codec

class FixEngine:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.codec = Codec()
        self.socket = None
        self.running = False
        self.logger = logging.getLogger('FixEngine')
        self.logger.setLevel(logging.DEBUG)

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.running = True
        self.logger.info(f"Connected to {self.host}:{self.port}")

    def disconnect(self):
        self.running = False
        if self.socket:
            self.socket.close()
            self.logger.info("Disconnected")

    def send_message(self, message):
        fix_message = FixMessage.from_dict(message)
        wire_message = fix_message.to_wire(codec=self.codec)
        self.socket.sendall(wire_message)
        self.logger.info(f"Sent: {fix_message}")

    def receive_message(self):
        while self.running:
            data = self.socket.recv(4096)
            if data:
                fix_message = FixMessage.from_wire(data, codec=self.codec)
                self.logger.info(f"Received: {fix_message}")
                self.handle_message(fix_message)

    def handle_message(self, message):
        # Implement message handling logic
        pass

    def start(self):
        self.connect()
        threading.Thread(target=self.receive_message).start()

    def stop(self):
        self.disconnect()

# Example usage
if __name__ == '__main__':
    engine = FixEngine('127.0.0.1', 9121)
    engine.start()

    # Example message
    message = {
        8: 'FIX.4.2',
        35: 'D',
        49: 'SENDER',
        56: 'TARGET',
        34: 1,
        52: '20250127-19:43:40',
        11: '12345',
        54: '1',
        38: '100',
        40: '2'
    }

    engine.send_message(message)
    engine.stop()
