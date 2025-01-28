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
from network import Acceptor, Initiator
from fixmessage_builder import FixMessageBuilder

class FixEngine:
    def __init__(self, host, port, seq_file='sequence.json', mode='initiator'):
        self.host = host
        self.port = port
        self.codec = Codec()
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
        self.network = Acceptor(host, port) if mode == 'acceptor' else Initiator(host, port)

    def connect(self):
        self.network.connect()

    def disconnect(self):
        self.network.disconnect()

    def send_message(self, message):
        fix_message = FixMessage.from_dict(message)
        # Populate tag 52 with the current sending time if not already present
        if not fix_message.anywhere(52):
            fix_message[52] = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        wire_message = fix_message.to_wire(codec=self.codec)
        self.network.send(wire_message)

    def receive_message(self):
        self.network.receive(self.handle_message)

    def handle_message(self, data):
        with self.lock:
            self.received_message.clear()
            self.received_message.from_wire(data, codec=self.codec)
            self.logger.info(f"Received: {self.received_message}")
            msg_type = self.received_message.get(35)
            if msg_type == 'A':  # Logon
                self.handle_logon(self.received_message)
            elif msg_type == '0':  # Heartbeat
                self.handle_heartbeat(self.received_message)
            elif msg_type == '1':  # Test Request
                self.handle_test_request(self.received_message)
            elif msg_type == '2':  # Resend Request
                self.handle_resend_request(self.received_message)
            elif msg_type == '5':  # Logout
                self.handle_logout(self.received_message)
            elif msg_type == 'D':  # New Order
                self.handle_new_order(self.received_message)
            elif msg_type == 'F':  # Cancel Request
                self.handle_cancel_order(self.received_message)
            else:
                self.logger.warning(f"Unknown message type: {msg_type}")

    def handle_logon(self, message):
        with self.lock:
            self.response_message = (FixMessageBuilder()
                                     .set_version('FIX.4.4')
                                     .set_msg_type('A')
                                     .set_sender('SERVER')
                                     .set_target(message.get(49))
                                     .set_sequence_number(self.sequence_manager.get_next_sequence_number())
                                     .set_sending_time()
                                     .build())
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
            self.response_message = (FixMessageBuilder()
                                     .set_version('FIX.4.4')
                                     .set_msg_type('5')  # Logout
                                     .set_sender('SERVER')
                                     .set_target(message.get(49))
                                     .set_sequence_number(self.sequence_manager.get_next_sequence_number())
                                     .set_sending_time()
                                     .build())
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
    message = (FixMessageBuilder()
               .set_version('FIX.4.4')
               .set_msg_type('D')
               .set_sender('SENDER')
               .set_target('TARGET')
               .set_sequence_number(1)
               .set_sending_time()
               .set_custom_field(11, engine.generate_clordid())  # Generate unique ClOrdID
               .set_custom_field(54, '1')
               .set_custom_field(38, '100')
               .set_custom_field(40, '2')
               .build())

    engine.send_message(message)
    engine.stop()
