import asyncio
import logging
from datetime import datetime
from pyfixmsg.fixmessage import FixMessage
from pyfixmsg.codecs.stringfix import Codec
import uuid  # For generating unique ClOrdID
from heartbeat import Heartbeat
from testrequest import send_test_request
from gapfill import send_gapfill
from sequence import SequenceManager
from network import Acceptor, Initiator
from fixmessage_factory import FixMessageFactory
from configmanager import ConfigManager  # Singleton ConfigManager
from event_notifier import EventNotifier  # Observer EventNotifier
from message_handler import (
    MessageProcessor, 
    LogonHandler, 
    ExecutionReportHandler, 
    NewOrderHandler, 
    CancelOrderHandler,
    OrderCancelReplaceHandler,
    OrderCancelRejectHandler,
    NewOrderMultilegHandler,
    MultilegOrderCancelReplaceHandler
)

class FixEngine:
    def __init__(self, config_manager, mode='initiator'):
        self.config_manager = config_manager
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
        self.message_processor = MessageProcessor()  # Initialize MessageProcessor

        # Register message handlers
        self.message_processor.register_handler('A', LogonHandler())
        self.message_processor.register_handler('8', ExecutionReportHandler())
        self.message_processor.register_handler('D', NewOrderHandler())
        self.message_processor.register_handler('F', CancelOrderHandler())
        self.message_processor.register_handler('G', OrderCancelReplaceHandler())
        self.message_processor.register_handler('9', OrderCancelRejectHandler())
        self.message_processor.register_handler('AB', NewOrderMultilegHandler())
        self.message_processor.register_handler('AC', MultilegOrderCancelReplaceHandler())
    
    async def connect(self):
        await self.network.connect()
    
    async def disconnect(self):
        await self.network.disconnect()
    
    async def send_message(self, message):
        fix_message = FixMessage.from_dict(message)
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
            
            await self.message_processor.process_message(self.received_message)
            msg_type = self.received_message.get(35)
            self.event_notifier.notify(msg_type, self.received_message)  # Notify subscribers
    
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
            if self.missed_heartbeats >= 1:
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
    message = FixMessageFactory.create_message(
        'D',
        sender=engine.sender,
        target=engine.target,
        clordid=engine.generate_clordid(),
        version=engine.version,
        sequence_number=1,
        sending_time=datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3],
        side='1',
        order_qty='100',
        order_type='2'
    )
    
    await engine.send_message(message)
    await asyncio.sleep(60)  # Run for 60 seconds
    await engine.stop()

if __name__ == '__main__':
    asyncio.run(main())
