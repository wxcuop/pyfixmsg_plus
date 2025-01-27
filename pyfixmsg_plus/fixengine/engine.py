import socket
import threading
import logging
from datetime import datetime
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
        self.heartbeat_interval = 30
        self.last_seq_num = 0
        self.response_message = FixMessage()  # Reusable FixMessage object

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
        msg_type = message.get(35)
        if msg_type == 'A':  # Logon
            self.handle_logon(message)
        elif msg_type == '0':  # Heartbeat
            self.handle_heartbeat(message)
        elif msg_type == '1':  # Test Request
            self.handle_test_request(message)
        elif msg_type == '2':  # Resend Request
            self.handle_resend_request(message)
        elif msg_type == '5':  # Logout
            self.handle_logout(message)
        elif msg_type == 'D':  # New Order
            self.handle_new_order(message)
        elif msg_type == 'F':  # Cancel Request
            self.handle_cancel_order(message)
        else:
            self.logger.warning(f"Unknown message type: {msg_type}")

    def handle_logon(self, message):
        self.response_message.clear()
        self.response_message.update({
            8: 'FIX.4.4',
            35: 'A',
            49: 'SERVER',
            56: message.get(49),
            34: self.last_seq_num + 1,
            52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        })
        self.send_message(self.response_message)

    def handle_heartbeat(self, message):
        self.logger.info("Heartbeat received")

    def handle_test_request(self, message):
        self.response_message.clear()
        self.response_message.update({
            8: 'FIX.4.4',
            35: '0',  # Heartbeat
            49: 'SERVER',
            56: message.get(49),
            34: self.last_seq_num + 1,
            52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        })
        self.send_message(self.response_message)

    def handle_resend_request(self, message):
        self.logger.info("Resend request received. Implement logic to resend messages.")

    def handle_logout(self, message):
        self.response_message.clear()
        self.response_message.update({
            8: 'FIX.4.4',
            35: '5',  # Logout
            49: 'SERVER',
            56: message.get(49),
            34: self.last_seq_num + 1,
            52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        })
        self.send_message(self.response_message)
        self.disconnect()

    def handle_new_order(self, message):
        self.logger.info("New order received. Implement order handling logic.")

    def handle_cancel_order(self, message):
        self.logger.info("Cancel order request received. Implement cancel order handling logic.")

    def start_heartbeat(self):
        while self.running:
            self.response_message.clear()
            self.response_message.update({
                8: 'FIX.4.4',
                35: '0',  # Heartbeat
                49: 'SERVER',
                56: 'CLIENT',
                34: self.last_seq_num + 1,
                52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            })
            self.send_message(self.response_message)
            time.sleep(self.heartbeat_interval)

    def start(self):
        self.connect()
        threading.Thread(target=self.receive_message).start()
        threading.Thread(target=self.start_heartbeat).start()

    def stop(self):
        self.disconnect()

# Example usage
if __name__ == '__main__':
    engine = FixEngine('127.0.0.1', 9121)
    engine.start()

    # Example message
    message = FixMessage()
    message.update({
        8: 'FIX.4.4',
        35: 'D',
        49: 'SENDER',
        56: 'TARGET',
        34: 1,
        52: '20250127-19:43:40',
        11: '12345',
        54: '1',
        38: '100',
        40: '2'
    })

    engine.send_message(message)
    engine.stop()
