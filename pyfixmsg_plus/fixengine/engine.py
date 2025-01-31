import asyncio
import logging
from datetime import datetime
from pyfixmsg.codecs.stringfix import Codec
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
    MultilegOrderCancelReplaceHandler,
    ResendRequestHandler,
    SequenceResetHandler,
    RejectHandler,
    LogoutHandler
)
from database_message_store import DatabaseMessageStore

class FixEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.host = self.config_manager.get('FIX', 'host', '127.0.0.1')
        self.port = int(self.config_manager.get('FIX', 'port', '5000'))
        self.sender = self.config_manager.get('FIX', 'sender', 'SENDER')
        self.target = self.config_manager.get('FIX', 'target', 'TARGET')
        self.version = self.config_manager.get('FIX', 'version', 'FIX.4.4')
        self.use_tls = self.config_manager.get('FIX', 'use_tls', 'false').lower() == 'true'
        self.mode = self.config_manager.get('FIX', 'mode', 'initiator').lower()
        db_path = self.config_manager.get('FIX', 'state_file', 'fix_state.db')
        
        self.codec = Codec()
        self.running = False
        self.logger = logging.getLogger('FixEngine')
        self.logger.setLevel(logging.DEBUG)
        self.heartbeat_interval = int(self.config_manager.get('FIX', 'heartbeat_interval', '30'))
        self.sequence_manager = SequenceManager(db_path)
        self.message_store = DatabaseMessageStore(db_path)  # Initialize message store
        self.response_message = FixMessageFactory.create_message('0')  # Reusable FixMessage object
        self.received_message = FixMessageFactory.create_message('0')  # Reusable FixMessage object for received messages
        self.lock = asyncio.Lock()  # Lock for thread safety
        self.heartbeat = Heartbeat(self.send_message, self.config_manager, self.heartbeat_interval)
        self.last_heartbeat_time = None
        self.missed_heartbeats = 0
        self.session_id = f"{self.host}:{self.port}"
        self.network = Acceptor(self.host, self.port, self.use_tls) if self.mode == 'acceptor' else Initiator(self.host, self.port, self.use_tls)
        
        self.event_notifier = EventNotifier()  # Initialize EventNotifier
        self.message_processor = MessageProcessor(self.message_store)  # Initialize MessageProcessor with message store

        # Register message handlers
        self.message_processor.register_handler('A', LogonHandler(self.message_store))
        self.message_processor.register_handler('8', ExecutionReportHandler(self.message_store))
        self.message_processor.register_handler('D', NewOrderHandler(self.message_store))
        self.message_processor.register_handler('F', CancelOrderHandler(self.message_store))
        self.message_processor.register_handler('G', OrderCancelReplaceHandler(self.message_store))
        self.message_processor.register_handler('9', OrderCancelRejectHandler(self.message_store))
        self.message_processor.register_handler('AB', NewOrderMultilegHandler(self.message_store))
        self.message_processor.register_handler('AC', MultilegOrderCancelReplaceHandler(self.message_store))
        self.message_processor.register_handler('2', ResendRequestHandler(self.message_store))
        self.message_processor.register_handler('4', SequenceResetHandler(self.message_store))
        self.message_processor.register_handler('3', RejectHandler(self.message_store))
        self.message_processor.register_handler('5', LogoutHandler(self.message_store))

    async def connect(self):
        await self.network.connect()

    async def disconnect(self):
        await self.network.disconnect()
        await self.heartbeat.stop()  # Stop the heartbeat when disconnecting

    async def send_message(self, message):
        fix_message = FixMessageFactory.create_message_from_dict(message)
        if not fix_message.anywhere(52):
            fix_message[52] = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        fix_message[34] = self.sequence_manager.get_next_sequence_number()  # Set sequence number
        wire_message = fix_message.to_wire(codec=self.codec)
        await self.network.send(wire_message)
        self.message_store.store_message(fix_message[34], 'outbound', wire_message)  # Store the sent message
        FixMessageFactory.return_message(fix_message)

    async def receive_message(self):
        await self.network.receive(self.handle_message)

    async def handle_message(self, data):
        async with self.lock:
            self.received_message.clear()
            self.received_message.from_wire(data, codec=self.codec)
            self.logger.info(f"Received: {self.received_message}")
            
            if self.received_message.checksum() != self.received_message[10]:
                self.logger.error("Checksum validation failed for received message.")
                await self.send_reject_message(self.received_message)
                return
            
            self.message_store.store_message(self.received_message[34], 'inbound', data)  # Store the received message
            await self.message_processor.process_message(self.received_message)
            msg_type = self.received_message.get(35)

            if msg_type == 'A':  # Logon
                await self.handle_logon()
                await self.heartbeat.start()  # Start the heartbeat after logon

            if msg_type == '1':  # Test Request
                await self.handle_test_request(self.received_message)

            self.event_notifier.notify(msg_type, self.received_message)  # Notify subscribers
