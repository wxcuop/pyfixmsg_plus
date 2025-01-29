import asyncio
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
from configmanager import ConfigManager  # Import the new ConfigManager
from events import EventNotifier  # Import EventNotifier

class FixEngine:
    def __init__(self, config_manager, mode='initiator'):
        self.config_manager = config_manager
        self.config_manager.load_config()

        self.host = self.config_manager.get('FIX', 'host', '127.0.0.1')
        self.port = int(self.config_manager.get('FIX', 'port', '5000'))
        self.sender = self.config_manager.get('FIX', 'sender', 'SENDER')
        self.target = self.config_manager.get('FIX', 'target', 'TARGET')
        self.version = self.config_manager.get('FIX', 'version', 'FIX.4.4')
        self.use_tls = self.config_manager.get('FIX', 'use_tls', 'false').lower() == 'true'
        seq_file = self.config_manager.get('FIX', 'state_file', 'sequence.json')
        
        self.codec = Codec()
        self.running = False
        self.logger = logging.getLogger('FixEngine')
        self.logger.setLevel(logging.DEBUG)
        self.heartbeat_interval = int(self.config_manager.get('FIX', 'heartbeat_interval', '30'))
        self.sequence_manager = SequenceManager(seq_file)
        self.response_message = FixMessage()  # Reusable FixMessage object
        self.received_message = FixMessage()  # Reusable FixMessage object for received messages
        self.lock = asyncio.Lock()  # Lock for thread safety
        self.heartbeat = Heartbeat(self.send_message, self.config_manager, self.heartbeat_interval)
        self.last_heartbeat_time = None
        self.missed_heartbeats = 0
        self.session_id = f"{self.host}:{self.port}"
        self.network = Acceptor(self.host, self.port, self.use_tls) if mode == 'acceptor' else Initiator(self.host, self.port, self.use_tls)
        
        self.event_notifier = EventNotifier()  # Initialize EventNotifier
    
    async def connect(self):
        await self.network.connect()
    
    async def disconnect(self):
        await self.network.disconnect()
    
    async def send_message(self, message):
        fix_message = FixMessage.from_dict(message)
        # Populate tag 52 with the current sending time if not already present
        if not fix_message.anywhere(52):
            fix_message[52] = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        wire_message = fix_message.to_wire(codec=self.codec)
        await self.network.send(wire_message)
    
    async def receive_message(self):
        await self.network.receive(self.handle_message)
    
    async def handle_message(self, data):
        async with self.lock:
            self.received_message.clear()
            self.received_message.from_wire(data, codec=self.codec)
            self.logger.info(f"Received: {self.received_message}")
            
            if self.received_message.checksum() != self.received_message[10]:
                self.logger.error("Checksum validation failed for received message.")
                return
            
            msg_type = self.received_message.get(35)
            
            handler = {
                'A': self.handle_logon,
                '0': self.handle_heartbeat,
                '1': self.handle_test_request,
                '2': self.handle_resend_request,
                '5': self.handle_logout,
                'D': self.handle_new_order,
                'F': self.handle_cancel_order,
                '8': self.handle_execution_report,
                'G': self.handle_order_cancel_replace,
                'AB': self.handle_new_order_multileg,
                'AC': self.handle_multileg_order_cancel_replace
            }.get(msg_type, self.handle_unknown_message)
            
            await handler(self.received_message)
            self.event_notifier.notify(msg_type, self.received_message)  # Notify subscribers
    
    async def handle_unknown_message(self, message):
        self.logger.warning(f"Unknown message type: {message.get(35)}")
    
    async def handle_logon(self, message):
        async with self.lock:
            self.response_message = (FixMessageBuilder()
                                     .set_version(self.version)
                                     .set_msg_type('A')
                                     .set_sender(self.sender)
                                     .set_target(message.get(49))
                                     .set_sequence_number(self.sequence_manager.get_next_sequence_number())
                                     .set_sending_time()
                                     .build())
            await self.send_message(self.response_message)
    
    async def handle_heartbeat(self, message):
        self.logger.info("Heartbeat received")
        self.last_heartbeat_time = time.time()
        await self.check_heartbeat()
    
    async def handle_test_request(self, message):
        await send_test_request(self.send_message, self.config_manager, message.get(49), self.sequence_manager.get_next_sequence_number())
    
    async def handle_resend_request(self, message):
        await send_gapfill(self.send_message, self.config_manager, message.get(49), self.sequence_manager.get_next_sequence_number(), self.sequence_manager.get_next_sequence_number() + 10)

    async def handle_logout(self, message):
        async with self.lock:
            self.response_message = (FixMessageBuilder()
                                     .set_version(self.version)
                                     .set_msg_type('5')  # Logout
                                     .set_sender(self.sender)
                                     .set_target(message.get(49))
                                     .set_sequence_number(self.sequence_manager.get_next_sequence_number())
                                     .set_sending_time()
                                     .build())
            await self.send_message(self.response_message)
            await self.disconnect()
    
    async def handle_new_order(self, message):
        self.logger.info("New order received. Implement order handling logic.")
    
    async def handle_cancel_order(self, message):
        self.logger.info("Cancel order request received. Implement cancel order handling logic.")
    
    async def handle_execution_report(self, message):
        self.logger.info("Execution report received. Implement execution report handling logic.")
    
    async def handle_order_cancel_replace(self, message):
        self.logger.info("Order cancel/replace request received. Implement order cancel/replace handling logic.")
    
    async def handle_new_order_multileg(self, message):
        self.logger.info("New order - Multileg received. Implement new order - multileg handling logic.")
    
    async def handle_multileg_order_cancel_replace(self, message):
        self.logger.info("Multileg order cancel/replace request received. Implement multileg order cancel/replace handling logic.")
    
    async def start(self):
        await self.connect()
        await self.heartbeat.start()
        asyncio.create_task(self.receive_message())
    
    async def stop(self):
        await self.heartbeat.stop()
        await self.disconnect()
    
    def generate_clordid(self):
        return str(uuid.uuid4())
    
    async def check_heartbeat(self):
        current_time = time.time()
        if self.last_heartbeat_time and current_time - self.last_heartbeat_time > self.heartbeat_interval:
            self.missed_heartbeats += 1
            self.logger.warning(f"Missed heartbeat {self.missed_heartbeats} times for {self.session_id}")
            
            if self.missed_heartbeats >= 1:  # Adjust threshold as needed
                test_req_id = f"TEST{int(current_time)}"
                await self.send_test_request(test_req_id)

# Example usage
async def main():
    config_manager = ConfigManager('config.ini')
    engine = FixEngine(config_manager)
    
    # Subscribe to events
    def logon_handler(message):
        print(f"Logon message received: {message}")

    def execution_report_handler(message):
        print(f"Execution report received: {message}")

    engine.event_notifier.subscribe('A', logon_handler)
    engine.event_notifier.subscribe('8', execution_report_handler)
    
    await engine.start()
    
    # Example message
    message = (FixMessageBuilder()
               .set_version(engine.version)
               .set_msg_type('D')
               .set_sender(engine.sender)
               .set_target(engine.target)
               .set_sequence_number(1)
               .set_sending_time()
               .set_custom_field(11, engine.generate_clordid())  # Generate unique ClOrdID
               .set_custom_field(54, '1')
               .set_custom_field(38, '100')
               .set_custom_field(40, '2')
               .build())
    
    await engine.send_message(message)
    await engine.stop()

if __name__ == '__main__':
    asyncio.run(main())
