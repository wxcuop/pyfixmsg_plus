import asyncio
import logging
from datetime import datetime, timezone
from heartbeat import Heartbeat, HeartbeatBuilder
from testrequest import TestRequest
from network import Acceptor, Initiator
from configmanager import ConfigManager
from event_notifier import EventNotifier
from message_handler import (
    MessageProcessor, 
    LogonHandler, 
    TestRequestHandler,  
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
    LogoutHandler,
    HeartbeatHandler
)
from message_store_factory import MessageStoreFactory
from state_machine import StateMachine, Disconnected, LogonInProgress, LogoutInProgress, Active, Reconnecting
from scheduler import Scheduler
from pyfixmsg.fixmessage import FixMessage
from pyfixmsg.spec import FixSpec
from pyfixmsg.codec import Codec
from pyfixmsg.fragment import FixFragment

class FixEngine:
    def __init__(self, config_manager, application):
        self.config_manager = config_manager
        self.application = application
        self.state_machine = StateMachine(Disconnected())
        self.state_machine.subscribe(self.on_state_change)
        self.host = self.config_manager.get('FIX', 'host', '127.0.0.1')
        self.port = int(self.config_manager.get('FIX', 'port', '5000'))
        self.sender = self.config_manager.get('FIX', 'sender', 'SENDER')
        self.target = self.config_manager.get('FIX', 'target', 'TARGET')
        self.version = self.config_manager.get('FIX', 'version', 'FIX.4.4')
        self.spec_filename = self.config_manager.get('FIX', 'spec_filename', 'FIX44.xml')
        self.use_tls = self.config_manager.get('FIX', 'use_tls', 'false').lower() == 'true'
        self.mode = self.config_manager.get('FIX', 'mode', 'initiator').lower()
        db_path = self.config_manager.get('FIX', 'state_file', 'fix_state.db')
        
        self.running = False
        self.logger = logging.getLogger('FixEngine')
        self.logger.setLevel(logging.DEBUG)
        self.heartbeat_interval = int(self.config_manager.get('FIX', 'heartbeat_interval', '30'))
        self.message_store = MessageStoreFactory.get_message_store('database', db_path)
        self.message_store.beginstring = self.version
        self.message_store.sendercompid = self.sender
        self.message_store.targetcompid = self.target
        self.lock = asyncio.Lock()
        self.heartbeat = (HeartbeatBuilder()
                          .set_send_message_callback(self.send_message)
                          .set_config_manager(self.config_manager)
                          .set_heartbeat_interval(self.heartbeat_interval)
                          .set_state_machine(self.state_machine)
                          .set_fix_engine(self)
                          .build())
        self.test_request = TestRequest(self.send_message, self.config_manager)
        self.last_heartbeat_time = None
        self.missed_heartbeats = 0
        self.session_id = f"{self.host}:{self.port}"
        self.network = Acceptor(self.host, self.port, self.use_tls) if self.mode == 'acceptor' else Initiator(self.host, self.port, self.use_tls)
        
        self.event_notifier = EventNotifier()
        self.message_processor = MessageProcessor(self.message_store, self.application)
        
        # Register message handlers
        self.message_processor.register_handler('A', LogonHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('1', TestRequestHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('8', ExecutionReportHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('D', NewOrderHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('F', CancelOrderHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('G', OrderCancelReplaceHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('9', OrderCancelRejectHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('AB', NewOrderMultilegHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('AC', MultilegOrderCancelReplaceHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('2', ResendRequestHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('4', SequenceResetHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('3', RejectHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('5', LogoutHandler(self.message_store, self.state_machine, self.application))
        self.message_processor.register_handler('0', HeartbeatHandler(self.message_store, self.state_machine, self.application))

        # Initialize scheduler
        self.scheduler = Scheduler(self.config_manager, self)
        self.scheduler_task = asyncio.create_task(self.scheduler.run_scheduler())

        # Retry and backoff strategy settings
        self.retry_interval = int(self.config_manager.get('FIX', 'retry_interval', '5'))
        self.max_retries = int(self.config_manager.get('FIX', 'max_retries', '5'))
        self.retry_attempts = 0

        # Load the FIX specification and create a codec
        self.spec = FixSpec(self.spec_filename)
        self.codec = Codec(spec=self.spec, fragment_class=FixFragment)

    def fixmsg(self, *args, **kwargs):
        """
        Factory function to create FixMessage instances with the codec.
        """
        message = FixMessage(*args, **kwargs)
        message.codec = self.codec
        return message

    def on_state_change(self, state_name):
        self.logger.info(f"State changed to: {state_name}")

    async def connect(self):
        try:
            self.state_machine.on_event('connect')
            if self.mode == 'acceptor':
                self.logger.info("Starting in acceptor mode, waiting for incoming connections...")
                await self.network.start_accepting(self.handle_incoming_connection)
            else:
                await self.network.connect()
                self.state_machine.on_event('logon')
                self.logger.info("Connected to FIX server.")
                await self.logon()
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            await self.retry_connect()

    async def retry_connect(self):
        if self.retry_attempts < self.max_retries:
            self.retry_attempts += 1
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying connection in {backoff_time} seconds (Attempt {self.retry_attempts}/{self.max_retries})...")
            await asyncio.sleep(backoff_time)
            await self.connect()
        else:
            self.logger.error("Max retries reached. Connection failed.")

    async def handle_incoming_connection(self, reader, writer):
        try:
            self.state_machine.on_event('logon')
            self.logger.info("Accepted incoming connection.")
            self.network.set_transport(reader, writer)
            await self.logon()
            await self.receive_message()
        except Exception as e:
            self.logger.error(f"Error handling incoming connection: {e}")
            self.state_machine.on_event('disconnect')
            writer.close()
            await writer.wait_closed()

    async def logon(self):
        if self.state_machine.state.name != 'ACTIVE' and self.state_machine.state.name != 'LOGON_IN_PROGRESS':
            self.logger.error("Cannot logon: not connected.")
            return
        try:
            logon_message = self.fixmsg()
            logon_message.update({
                35: 'A',  # MsgType
                49: self.sender,  # SenderCompID
                56: self.target,  # TargetCompID
                34: self.message_store.get_next_outgoing_sequence_number()  # MsgSeqNum
            })
            await self.send_message(logon_message)
            await self.heartbeat.start()
        except Exception as e:
            self.logger.error(f"Failed to logon: {e}")
            await self.retry_logon()

    async def retry_logon(self):
        if self.retry_attempts < self.max_retries:
            self.state_machine.on_event('reconnect')
            self.retry_attempts += 1
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying logon in {backoff_time} seconds (Attempt {self.retry_attempts}/{self.max_retries})...")
            await asyncio.sleep(backoff_time)
            await self.logon()
        else:
            self.logger.error("Max retries reached. Logon failed.")

    async def send_message(self, message):
        message.update({
            52: datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3],  # SendingTime
            34: self.message_store.get_next_outgoing_sequence_number()  # MsgSeqNum
        })
        wire_message = message.to_wire(codec=self.codec)
        await self.network.send(wire_message)
        self.message_store.store_message(self.version, self.sender, self.target, message[34], wire_message)

    async def receive_message(self):
        try:
            while self.state_machine.state.name == 'ACTIVE':
                data = await self.network.receive()
                await self.handle_message(data)
        except Exception as e:
            self.logger.error(f"Error receiving message: {e}")
            await self.disconnect()

    async def send_reject_message(self, ref_seq_num, ref_tag_id, session_reject_reason, text):
        reject_message = self.fixmsg()
        reject_message.update({
            35: '3',  # MsgType
            49: self.sender,  # SenderCompID
            56: self.target,  # TargetCompID
            34: self.message_store.get_next_outgoing_sequence_number()  # MsgSeqNum
        })
        await self.send_message(reject_message)
        self.message_store.set_incoming_sequence_number(ref_seq_num + 1)
        self.logger.info(f"Sent Reject message for sequence number {ref_seq_num} with reason {session_reject_reason}")

    async def handle_message(self, data):
        async with self.lock:
            try:
                self.received_message = self.fixmsg().from_wire(data, codec=self.codec)
            except Exception as e:
                self.logger.error(f"Failed to parse message: {e}")
                await self.send_reject_message(self.message_store.get_next_incoming_sequence_number(), 0, 99, "Failed to parse message")
                return
    
            self.logger.info(f"Received: {self.received_message}")
    
            if self.received_message.checksum() != self.received_message[10]:
                self.logger.error("Checksum validation failed for received message.")
                await self.send_reject_message(self.received_message[34], 10, 5, "Invalid checksum")
                return
    
            expected_seq_num = self.message_store.get_next_incoming_sequence_number()
            received_seq_num = self.received_message[34]
            if received_seq_num != expected_seq_num:
                self.logger.warning(f"Sequence number gap detected. Expected: {expected_seq_num}, Received: {received_seq_num}")
                await self.message_processor.get_handler('2').handle_resend_request(self.received_message, self.send_message)
                return
    
            self.message_store.store_message(self.version, self.sender, self.target, self.received_message[34], data)
            self.message_store.set_incoming_sequence_number(self.received_message[34] + 1)
    
            await self.message_processor.process_message(self.received_message)

    async def reset_sequence_numbers(self):
        self.message_store.reset_sequence_numbers()
        self.logger.info("Sequence numbers reset to 1 for both inbound and outbound.")

    async def set_inbound_sequence_number(self, seq_num):
        self.message_store.set_incoming_sequence_number(seq_num)
        self.logger.info(f"Inbound sequence number set to {seq_num}")

    async def set_outbound_sequence_number(self, seq_num):
        self.message_store.set_outgoing_sequence_number(seq_num)
        self.logger.info(f"Outbound sequence number set to {seq_num}")

    async def handle_logout(self, message):
        self.logger.info("Received Logout message.")
        await self.send_logout_message()
        self.state_machine.on_event('disconnect')
        await self.network.disconnect()

    async def send_logout_message(self):
        logout_message = self.fixmsg()
        logout_message.update({
            35: '5',  # MsgType
            49: self.sender,  # SenderCompID
            56: self.target,  # TargetCompID
            34: self.message_store.get_next_outgoing_sequence_number()  # MsgSeqNum
        })
        await self.send_message(logout_message)
        self.logger.info("Sent Logout message.")

# Example usage
# if __name__ == "__main__":
#     config_manager = ConfigManager()
#     application = MyApplication()  # Replace MyApplication with your concrete implementation
#     engine = FixEngine(config_manager, application)
#     asyncio.run(engine.connect())
#     # Example of setting sequence numbers
#     asyncio.run(engine.set_inbound_sequence_number(100))
#     asyncio.run(engine.set_outbound_sequence_number(200))
