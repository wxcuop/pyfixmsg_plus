import asyncio
import logging
from datetime import datetime, timezone
from pyfixmsg_plus.fixengine.heartbeat import Heartbeat
from pyfixmsg_plus.fixengine.heartbeat_builder import HeartbeatBuilder
from pyfixmsg_plus.fixengine.testrequest import TestRequest
from pyfixmsg_plus.fixengine.network import Acceptor, Initiator
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.events import EventNotifier
from pyfixmsg_plus.fixengine.message_handler import (
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
from pyfixmsg_plus.fixengine.message_store_factory import MessageStoreFactory
from pyfixmsg_plus.fixengine.state_machine import StateMachine, Disconnected, LogonInProgress, LogoutInProgress, Active, Reconnecting
from pyfixmsg_plus.fixengine.scheduler import Scheduler
from pyfixmsg.fixmessage import FixMessage
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec
from pyfixmsg.fixmessage import FixFragment

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
        
        self.running = False # This engine's running flag, distinct from network.running
        self.logger = logging.getLogger('FixEngine')
        # Ensure logger level is set, e.g., from config or default to INFO/DEBUG
        # self.logger.setLevel(logging.DEBUG) # Or set based on a config setting

        self.heartbeat_interval = int(self.config_manager.get('FIX', 'heartbeat_interval', '30'))
        self.message_store = MessageStoreFactory.get_message_store('database', db_path)
        self.message_store.beginstring = self.version
        self.message_store.sendercompid = self.sender
        self.message_store.targetcompid = self.target
        self.lock = asyncio.Lock() # General lock for FixEngine critical sections if needed
        self.heartbeat = (HeartbeatBuilder()
                          .set_send_message_callback(self.send_message)
                          .set_config_manager(self.config_manager)
                          .set_heartbeat_interval(self.heartbeat_interval)
                          .set_state_machine(self.state_machine)
                          .set_fix_engine(self)
                          .build())
        self.test_request = TestRequest(self.send_message, self.config_manager)
        self.last_heartbeat_time = None # Potentially managed by Heartbeat class itself
        self.missed_heartbeats = 0 # Potentially managed by Heartbeat class itself
        self.session_id = f"{self.host}:{self.port}"
        self.network = Acceptor(self.host, self.port, self.use_tls) if self.mode == 'acceptor' else Initiator(self.host, self.port, self.use_tls)
        
        self.event_notifier = EventNotifier()
        self.message_processor = MessageProcessor(self.message_store, self.state_machine, self.application, self) 
        
        self.message_processor.register_handler('A', LogonHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('1', TestRequestHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('8', ExecutionReportHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('D', NewOrderHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('F', CancelOrderHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('G', OrderCancelReplaceHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('9', OrderCancelRejectHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('AB', NewOrderMultilegHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('AC', MultilegOrderCancelReplaceHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('2', ResendRequestHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('4', SequenceResetHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('3', RejectHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('5', LogoutHandler(self.message_store, self.state_machine, self.application, self))
        self.message_processor.register_handler('0', HeartbeatHandler(self.message_store, self.state_machine, self.application, self))

        self.scheduler = Scheduler(self.config_manager, self)
        self.scheduler_task = asyncio.create_task(self.scheduler.run_scheduler())

        self.retry_interval = int(self.config_manager.get('FIX', 'retry_interval', '5'))
        self.max_retries = int(self.config_manager.get('FIX', 'max_retries', '5'))
        self.retry_attempts = 0

        self.spec = FixSpec(self.spec_filename)
        self.codec = Codec(spec=self.spec, fragment_class=FixFragment)

    def fixmsg(self, *args, **kwargs):
        message = FixMessage(*args, **kwargs)
        message.codec = self.codec
        return message

    def on_state_change(self, state_name):
        self.logger.info(f"State changed to: {state_name}")
        if state_name == 'LOGON_IN_PROGRESS':
            self.logger.debug("Logon process has started.")
        elif state_name == 'ACTIVE':
            self.logger.info("Connection is now ACTIVE.") # Changed to INFO for better visibility
            # Heartbeat start is now managed by LogonHandler or self.logon() for initiator
        elif state_name == 'DISCONNECTED':
            self.logger.info("Connection has been DISCONNECTED.") # Changed to INFO
            if self.heartbeat and self.heartbeat.is_running(): # Added self.heartbeat check
                 self.logger.debug("Stopping heartbeat task due to disconnect.")
                 asyncio.create_task(self.heartbeat.stop())


    async def connect(self):
        try:
            if self.mode == 'acceptor':
                self.logger.info(f"Acceptor starting on {self.host}:{self.port}...")
                await self.network.start_accepting(self.handle_incoming_connection)
                # start_accepting is blocking, so code here is reached on server stop.
                self.logger.info("Acceptor has stopped.")
            else: # Initiator mode
                self.logger.info(f"Initiator connecting to {self.host}:{self.port}...")
                self.state_machine.on_event('connecting') # More specific initial event
                await self.network.connect()
                self.logger.info("Initiator TCP connected. Proceeding with FIX Logon.")
                self.state_machine.on_event('logon_initiated') # State indicating we are about to send Logon
                await self.logon() # Initiator sends its Logon
                # The receive_message loop should start to get the Logon response and subsequent messages.
                await self.receive_message()
        except ConnectionRefusedError as e:
            self.logger.error(f"Connection refused when trying to connect to {self.host}:{self.port}: {e}")
            if self.mode == 'initiator':
                await self.retry_connect()
        except Exception as e:
            self.logger.error(f"Failed to connect or run FIX engine: {e}", exc_info=True)
            if self.mode == 'initiator': # Retry only makes sense for initiator
                await self.retry_connect()
            # For acceptor, if start_accepting fails, it might need a different recovery or just exit.

    async def retry_connect(self): # Primarily for initiator
        if self.mode == 'acceptor':
            self.logger.warning("Retry connect called in acceptor mode. This is not typical.")
            return

        if self.state_machine.state.name == 'DISCONNECTED' and self.retry_attempts < self.max_retries:
            self.retry_attempts += 1
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying connection in {backoff_time} seconds (Attempt {self.retry_attempts}/{self.max_retries})...")
            await asyncio.sleep(backoff_time)
            await self.connect() # Retry the whole connect sequence
        elif self.retry_attempts >= self.max_retries:
            self.logger.error("Max retries reached. Connection failed permanently for this attempt.")
            # Application might want to be notified here or take other actions.
        # If not DISCONNECTED, maybe it's already trying to connect or is connected.

    async def handle_incoming_connection(self, reader, writer):
        client_address_info = writer.get_extra_info('peername')
        client_address = f"{client_address_info[0]}:{client_address_info[1]}" if client_address_info else "unknown client"
        self.logger.info(f"Accepted incoming connection from {client_address}.")
        
        try:
            await self.network.set_transport(reader, writer)
            self.state_machine.on_event('tcp_connected') # New client connected (for acceptor)
            self.logger.info(f"Transport set for {client_address}. Waiting for Logon...")
            await self.receive_message()
        except ConnectionResetError:
            self.logger.warning(f"Connection reset by {client_address}.")
        except asyncio.IncompleteReadError:
            self.logger.warning(f"Incomplete read from {client_address}, connection closed prematurely.")
        except Exception as e:
            self.logger.error(f"Error handling incoming connection from {client_address}: {e}", exc_info=True)
        finally:
            self.logger.info(f"Cleaning up connection with {client_address}.")
            if writer and not writer.is_closing():
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as e_close:
                    self.logger.error(f"Error during writer.wait_closed() for {client_address}: {e_close}")
            
            if self.state_machine.state.name != 'DISCONNECTED':
                 self.logger.info(f"Setting state to DISCONNECTED for session with {client_address}")
                 self.state_machine.on_event('disconnect') # Ensure state reflects end of this client session
            self.logger.info(f"Connection with {client_address} ended.")


    async def logon(self): # This is ONLY for the INITIATOR to send its initial Logon
        if self.mode == 'acceptor':
            self.logger.error("CRITICAL: Acceptor attempted to call FixEngine.logon(). This is incorrect.")
            return

        if self.state_machine.state.name not in ['LOGON_INITIATED', 'RECONNECTING_LOGON']: # Allow logon if we just reconnected
            self.logger.warning(f"Cannot initiate logon: State is {self.state_machine.state.name}, expected LOGON_INITIATED or similar. Aborting logon attempt.")
            return

        try:
            self.logger.info("Initiator constructing and sending Logon message...")
            logon_message = self.fixmsg()
            logon_message.update({
                35: 'A',
                49: self.sender,
                56: self.target,
                34: self.message_store.get_next_outgoing_sequence_number(),
                108: self.heartbeat_interval,
                # Standard Logon fields often include:
                # 98: 0,  # EncryptMethod: 0=None/Other
                # 141: 'Y' # ResetSeqNumFlag: Consider 'Y' for robust startup, or 'N' if resuming.
                          # If 'Y', message_store sequence numbers should be reset before this.
            })
            if self.config_manager.get('FIX', 'reset_seq_num_on_logon', 'false').lower() == 'true':
                logon_message[141] = 'Y' # ResetSeqNumFlag
                await self.reset_sequence_numbers() # Reset local sequence numbers if flag is Y
                logon_message[34] = 1 # MsgSeqNum must be 1 if ResetSeqNumFlag=Y

            await self.send_message(logon_message)
            self.logger.info(f"Initiator Logon message sent (SeqNum {logon_message[34]}). Current state: {self.state_machine.state.name}. Starting heartbeat mechanism.")
            await self.heartbeat.start() 
            # State remains LOGON_INITIATED (or similar) until Logon response from acceptor moves it to ACTIVE via LogonHandler.
        except Exception as e:
            self.logger.error(f"Failed to send Logon message: {e}", exc_info=True)
            self.state_machine.on_event('logon_failed') 
            # Consider if disconnect or retry_logon should be called here.
            # If send fails, TCP might be down. retry_connect might be better.
            await self.disconnect(graceful=False) # Disconnect if we can't even send Logon


    async def retry_logon(self): # This might be better merged into retry_connect logic
        # This method seems redundant if retry_connect handles the full cycle.
        # Kept for now if specific logon retry logic is needed separate from TCP reconnect.
        self.logger.warning("retry_logon called. Consider merging with retry_connect.")
        if self.mode == 'acceptor': return

        if self.retry_attempts < self.max_retries: # Use self.retry_attempts from engine
            self.state_machine.on_event('reconnecting_logon') # Specific state for retrying logon
            self.retry_attempts += 1
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying logon in {backoff_time} seconds (Attempt {self.retry_attempts}/{self.max_retries})...")
            await asyncio.sleep(backoff_time)
            
            if not self.network.running:
                self.logger.info("Connection lost before logon retry. Attempting to reconnect first.")
                await self.connect() # This will attempt full connection and then logon
            else:
                 # If network is running, implies TCP is up, but previous logon failed at FIX level.
                 self.logger.info("Network seems up. Retrying sending Logon.")
                 await self.logon() # Try sending Logon again
        else:
            self.logger.error("Max retries reached for logon. Logon failed.")
            self.state_machine.on_event('disconnect')


    async def send_message(self, message: FixMessage):
        if self.state_machine.state.name == 'DISCONNECTED':
            self.logger.warning(f"Cannot send message (type {message.get(35)}): Session is DISCONNECTED.")
            return

        # Ensure standard header fields are set
        message[49] = self.sender   # SenderCompID
        message[56] = self.target   # TargetCompID
        # BeginString(8) and BodyLength(9) are handled by to_wire()

        # SendingTime(52)
        message[52] = datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3]
        
        # MsgSeqNum(34)
        if 34 not in message or (message.get(35) == 'A' and message.get(141) == 'Y' and message[34] != 1) : # Special case for Logon with ResetSeqNumFlag
            if message.get(35) == 'A' and message.get(141) == 'Y':
                message[34] = 1 # If ResetSeqNumFlag=Y on Logon, MsgSeqNum must be 1
            else:
                message[34] = self.message_store.get_next_outgoing_sequence_number()
        
        wire_message = message.to_wire(codec=self.codec)
        try:
            await self.network.send(wire_message)
            # Store message *after* successful send
            self.message_store.store_message(
                self.version, self.sender, self.target, 
                message[34], 
                wire_message.decode(errors='replace') # Store the string representation
            )
            self.logger.info(f"Sent: {message.get(35)} (SeqNum {message[34]})")
            if message.get(35) != '0': # Don't log every heartbeat content unless DEBUG
                 self.logger.debug(f"Sent Details: {message.to_wire(pretty=True)}")

        except ConnectionResetError as e:
            self.logger.error(f"ConnectionResetError while sending message (type {message.get(35)}, seq {message.get(34)}): {e}")
            await self.disconnect(graceful=False)
        except Exception as e:
            self.logger.error(f"Exception while sending message (type {message.get(35)}, seq {message.get(34)}): {e}", exc_info=True)
            # Depending on error, might need to disconnect
            await self.disconnect(graceful=False)


    async def receive_message(self):
        if not self.network.running:
            self.logger.warning("Network is not running at the start of receive_message. Cannot receive.")
            if self.state_machine.state.name != 'DISCONNECTED':
                await self.disconnect(graceful=False)
            return

        try:
            await self.network.receive(self.handle_message)
        except ConnectionResetError: # This might be caught by network.receive's loop too
            self.logger.warning("Receive loop terminated by FixEngine: Connection reset.")
            await self.disconnect(graceful=False)
        except asyncio.IncompleteReadError:
            self.logger.warning("Receive loop terminated by FixEngine: Incomplete read, connection closed.")
            await self.disconnect(graceful=False)
        except Exception as e:
            self.logger.error(f"Critical error in FixEngine's receive_message infrastructure: {e}", exc_info=True)
            await self.disconnect(graceful=False)
        finally:
            self.logger.info("FixEngine's receive_message loop has ended.")
            if self.state_machine.state.name != 'DISCONNECTED':
                self.state_machine.on_event('disconnect')


    async def send_reject_message(self, ref_seq_num, ref_tag_id, session_reject_reason, text, ref_msg_type=None):
        self.logger.info(f"Preparing to send Session Reject for RefSeqNum {ref_seq_num}, RefTagID {ref_tag_id}, Reason {session_reject_reason}, Text: {text}")
        reject_message = self.fixmsg()
        reject_message.update({
            35: '3',
            45: ref_seq_num, 
            58: text 
        })
        if ref_tag_id: # RefTagID is optional
            reject_message[371] = ref_tag_id
        if ref_msg_type: # RefMsgType is optional
             reject_message[372] = ref_msg_type
        if session_reject_reason is not None: # SessionRejectReason is optional but good to include
            reject_message[373] = session_reject_reason
        
        await self.send_message(reject_message)
        self.logger.info(f"Sent Session Reject for RefSeqNum {ref_seq_num}.")


    async def handle_message(self, data_str: str):
        async with self.lock:
            parsed_message = None
            try:
                parsed_message = self.fixmsg().from_wire(data_str, codec=self.codec)
            except Exception as e:
                self.logger.error(f"Failed to parse message string: '{data_str[:150]}...' Error: {e}", exc_info=True)
                # Cannot reliably send a Reject if parsing failed fundamentally.
                # Consider disconnecting. For now, just return.
                return
    
            msg_type = parsed_message.get(35)
            received_seq_num_str = parsed_message.get(34)
            self.logger.info(f"Received: {msg_type} (Seq {received_seq_num_str})")
            self.logger.debug(f"Received Details: {parsed_message.to_wire(pretty=True)}")

            # TODO: Implement checksum validation if not automatically handled by from_wire and raising an exception.
            # if not parsed_message.is_checksum_valid(): # Conceptual
            #     self.logger.error("Checksum validation FAILED for received message. Disconnecting.")
            #     await self.disconnect(graceful=False)
            #     return

            if not received_seq_num_str or not received_seq_num_str.isdigit():
                reason = f"Invalid or missing MsgSeqNum (34) in received message: '{received_seq_num_str}'"
                self.logger.error(reason)
                await self.send_logout_message(text=reason)
                await self.disconnect(graceful=False)
                return
            
            received_seq_num = int(received_seq_num_str)

            # --- Sequence Number Processing ---
            # For Logon (A), Logout (5), and SequenceReset-Reset(4, 123=N), sequence number rules are special
            # and largely handled by their respective handlers or initial session logic.
            # All other messages must follow strict sequence numbering.
            if msg_type not in ['A', '5'] and not (msg_type == '4' and parsed_message.get(123) == 'N'):
                expected_seq_num = self.message_store.get_next_incoming_sequence_number()

                if received_seq_num < expected_seq_num:
                    poss_dup_flag = parsed_message.get(43, 'N') # PossDupFlag
                    if poss_dup_flag == 'Y':
                        self.logger.info(f"Received PossDup message {msg_type} with SeqNum {received_seq_num} (expected {expected_seq_num}). Application should handle if it's a resend of an already processed message.")
                        # Application should decide whether to re-process or ignore.
                        # For now, we will process it via the handler. The handler or app layer should be idempotent.
                    else:
                        self.logger.warning(f"MsgSeqNum too low. Expected: {expected_seq_num}, Received: {received_seq_num}. Not PossDup. Message: {data_str}")
                        text = f"MsgSeqNum too low, expected {expected_seq_num} but received {received_seq_num}"
                        await self.send_logout_message(text=text)
                        await self.disconnect(graceful=False)
                        return 
                
                elif received_seq_num > expected_seq_num:
                    self.logger.warning(f"MsgSeqNum too high (Gap Detected). Expected: {expected_seq_num}, Received: {received_seq_num}. Initiating Resend Request.")
                    resend_request_msg = self.fixmsg()
                    resend_request_msg.update({
                        35: '2', # MsgType: Resend Request
                        7: expected_seq_num, # BeginSeqNo
                        16: 0 # EndSeqNo: 0 means all messages from BeginSeqNo up to current latest.
                               # Some systems prefer EndSeqNo = received_seq_num - 1.
                               # Using 0 is a common and robust approach.
                    })
                    await self.send_message(resend_request_msg)
                    # DO NOT process the current parsed_message as it's out of sequence.
                    return # Wait for the resent messages.
            
            # If sequence is okay (or handled by specific message type logic like Logon)
            # Store the raw message string *before* processing by handler
            # This ensures message is stored even if handler fails.
            self.message_store.store_message(
                self.version, self.sender, self.target, 
                received_seq_num, 
                data_str 
            )
            
            # Update incoming sequence number *after* successful validation and *before* processing by handler,
            # unless it's a SequenceReset-Reset (123=N) which manages its own seq num update in its handler.
            if not (msg_type == '4' and parsed_message.get(123) == 'N'):
                # For Logon messages, the LogonHandler should verify the sequence number
                # and then explicitly set the store's next incoming if valid.
                # For other messages that passed seq num checks, we can set it here.
                if msg_type != 'A': # Defer sequence setting for Logon to LogonHandler
                     self.message_store.set_incoming_sequence_number(received_seq_num + 1)
            
            await self.message_processor.process_message(parsed_message)

    async def disconnect(self, graceful=True):
        current_state = self.state_machine.state.name
        self.logger.info(f"Disconnect requested. Graceful: {graceful}. Current state: {current_state}.")

        if current_state == 'DISCONNECTED' and not self.network.running: # Check network too
            self.logger.info("Already disconnected.")
            return

        if graceful and current_state == 'ACTIVE':
            try:
                self.logger.info("Attempting graceful logout by sending Logout message.")
                await self.send_logout_message() # Default text will be used
                # After sending logout, we should wait for a response or timeout,
                # but for simplicity here, we proceed to disconnect TCP.
                # A more robust implementation would have a "LogoutInProgress" state.
            except Exception as e_logout:
                self.logger.error(f"Error sending logout message during graceful disconnect: {e_logout}")
        
        self.state_machine.on_event('disconnect_initiated') # Indicate we are starting disconnect process

        if self.network:
            self.logger.debug("Disconnecting network layer.")
            await self.network.disconnect() 
        
        if self.heartbeat and self.heartbeat.is_running():
            self.logger.debug("Stopping heartbeat.")
            await self.heartbeat.stop()

        if self.scheduler_task and not self.scheduler_task.done():
            self.logger.debug("Cancelling scheduler task.")
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                self.logger.info("Scheduler task cancelled successfully.")
        
        self.retry_attempts = 0 
        if current_state != 'DISCONNECTED':
            self.state_machine.on_event('disconnect') 
        self.logger.info("FIX Engine disconnected successfully.")


    async def reset_sequence_numbers(self):
        self.logger.info("Resetting sequence numbers to 1 for both inbound and outbound.")
        self.message_store.reset_sequence_numbers()
        # This should be called typically before a Logon with ResetSeqNumFlag=Y

    async def set_inbound_sequence_number(self, seq_num: int): # Added type hint
        self.logger.info(f"Externally setting inbound sequence number to {seq_num}.")
        self.message_store.set_incoming_sequence_number(seq_num)

    async def set_outbound_sequence_number(self, seq_num: int): # Added type hint
        self.logger.info(f"Externally setting outbound sequence number to {seq_num}.")
        self.message_store.set_outgoing_sequence_number(seq_num)

    # This method seems like it should be part of the LogoutHandler's logic,
    # or called by MessageProcessor when a Logout message (type '5') is received.
    # Keeping it here if engine needs to directly act on received logout for some reason,
    # but typically LogoutHandler would call engine.disconnect().
    async def handle_logout_message_received(self, message: FixMessage): 
        self.logger.info(f"Logout message received from counterparty: {message.get(58, '')}")
        if self.state_machine.state.name == 'ACTIVE': 
            self.logger.info("Responding to counterparty's Logout with our own Logout.")
            await self.send_logout_message(text="Logout Acknowledged") 
        
        # Regardless of sending a confirm, the session is now terminated.
        await self.disconnect(graceful=False) # False, as they initiated the logout.

    async def send_logout_message(self, text: str = "Operator requested logout"):
        current_state = self.state_machine.state.name
        if current_state == 'DISCONNECTED' and not self.network.running:
            self.logger.info("Cannot send Logout: Already disconnected and network not running.")
            return
        
        # Avoid sending multiple logouts if already in a logout process
        if current_state == 'LOGOUT_IN_PROGRESS':
            self.logger.info("Cannot send Logout: Logout already in progress.")
            return

        self.logger.info(f"Sending Logout message. Text: '{text}'")
        logout_message = self.fixmsg()
        logout_message.update({
            35: '5',
            58: text
        })
        
        try:
            # If we are initiating the logout, set state before sending
            if current_state != 'DISCONNECTED': # Avoid changing state if already trying to clean up disconnected session
                 self.state_machine.on_event('logout_sent') # Or a more specific "logout_initiated_by_us"

            await self.send_message(logout_message)
            self.logger.info(f"Successfully sent Logout message (SeqNum {logout_message.get(34)}).")
        except Exception as e:
            self.logger.error(f"Failed to send Logout message: {e}", exc_info=True)
            # If sending logout fails, we should still proceed to disconnect TCP.
        finally:
            # Disconnect TCP after sending logout, or if send fails.
            # The disconnect method will handle further state changes to DISCONNECTED.
            # This ensures that even if send_message fails, we attempt to clean up.
            # However, if send_message itself calls disconnect on failure, this might be redundant.
            # For now, let disconnect() be the final arbiter of the DISCONNECTED state.
            # If we initiated the logout, we should disconnect.
            # If we are responding to a logout, disconnect is also appropriate.
             if current_state != 'DISCONNECTED': # Only call disconnect if not already in that state from a failure in send_message
                await self.disconnect(graceful=False) # False, as we are now forcing the end of session.
