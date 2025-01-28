import socket
import threading
import logging
from datetime import datetime
from pyfixmsg.fixmessage import FixMessage
from pyfixmsg.codecs.stringfix import Codec
import uuid  # For generating unique ClOrdID
from heartbeat import Heartbeat
from testrequest import send_test_request
from gapfill import send_gapfill
import time
from sequence import SequenceManager

class FixEngine:
    def __init__(self, host, port, seq_file='sequence.json'):
        self.host = host
        self.port = port
        self.codec = Codec()
        self.socket = None
        self.running = False
        self.logger = logging.getLogger('FixEngine')
        self.logger.setLevel(logging.DEBUG)
        self.heartbeat_interval = 30
        self.sequence_manager = SequenceManager(seq_file)
        self.response_message = FixMessage()  # Reusable FixMessage object
        self.received_message = FixMessage()  # Reusable FixMessage object for received messages
        self.lock = threading.Lock()  # Lock for thread safety
        self.heartbeat = Heartbeat(self.send_message, self.heartbeat_interval)
        self.last_heartbeat_time = None
        self.missed_heartbeats = 0
        self.session_id = f"{host}:{port}"

    def connect(self):
        with self.lock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            self.logger.info(f"Connected to {self.host}:{self.port}")

    def disconnect(self):
        with self.lock:
            self.running = False
            if self.socket:
                self.socket.close()
            self.logger.info("Disconnected")

    def send_message(self, message):
        with self.lock:
            fix_message = FixMessage.from_dict(message)
            wire_message = fix_message.to_wire(codec=self.codec)
            self.socket.sendall(wire_message)
            self.logger.info(f"Sent: {fix_message}")

    def receive_message(self):
        while self.running:
            data = self.socket.recv(4096)
            if data:
                with self.lock:
                    self.received_message.clear()
                    self.received_message.from_wire(data, codec=self.codec)
                    self.logger.info(f"Received: {self.received_message}")
                    self.handle_message(self.received_message)

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
        with self.lock:
            self.response_message.clear()
            self.response_message.update({
                8: 'FIX.4.4',
                35: 'A',
                49: 'SERVER',
                56: message.get(49),
                34: self.sequence_manager.get_next_sequence_number(),
                52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            })
            self.send_message(self.response_message)

    def handle_heartbeat(self, message):
        self.logger.info("Heartbeat received")
        self.last_heartbeat_time = time.time()
        self.check_heartbeat()

    def handle_test_request(self, message):
        send_test_request(self.send_message, message.get(49), self.sequence_manager.get_next_sequence_number())

    def handle_resend_request(self, message):
        send_gapfill(self.send_message, message.get(49), self.sequence_manager.get_next_sequence_number(), self.sequence_manager.get_next_sequence_number() + 10)

    def handle_logout(self, message):
        with self.lock:
            self.response_message.clear()
            self.response_message.update({
                8: 'FIX.4.4',
                35: '5',  # Logout
                49: 'SERVER',
                56: message.get(49),
                34: self.sequence_manager.get_next_sequence_number(),
                52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            })
            self.send_message(self.response_message)
            self.disconnect()

    def handle_new_order(self, message):
        self.logger.info("New order received. Implement order handling logic.")

    def handle_cancel_order(self, message):
        self.logger.info("Cancel order request received. Implement cancel order handling logic.")

    def start(self):
        self.connect()
        self.heartbeat.start()
        threading.Thread(target=self.receive_message).start()

    def stop(self):
        self.heartbeat.stop()
        self.disconnect()

    def generate_clordid(self):
        return str(uuid.uuid4())

    def check_heartbeat(self):
        """
        Checks if a heartbeat was received within the expected interval.
        If not, sends a Test Request.
        """
        current_time = time.time()
        if self.last_heartbeat_time and current_time - self.last_heartbeat_time > self.heartbeat_interval:
            self.missed_heartbeats += 1
            self.logger.warning(f"Missed heartbeat {self.missed_heartbeats} times for {self.session_id}")
            
            if self.missed_heartbeats >= 1:  # Adjust threshold as needed
                test_req_id = f"TEST{int(current_time)}"
                self.send_test_request(test_req_id)

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
        11: engine.generate_clordid(),  # Generate unique ClOrdID
        54: '1',
        38: '100',
        40: '2'
    })

    engine.send_message(message)
    engine.stop()
