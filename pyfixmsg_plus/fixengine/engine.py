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
# Assuming your refined StateMachine is in this path
from pyfixmsg_plus.fixengine.state_machine import (
    StateMachine, Disconnected, Connecting, LogonInProgress, 
    AwaitingLogon, Active, LogoutInProgress, Reconnecting
)
from pyfixmsg_plus.fixengine.scheduler import Scheduler
from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec


class FixEngine:
    def __init__(self, config_manager, application):
        self.config_manager = config_manager
        self.application = application
        # Initialize with Disconnected state
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

        self.logger = logging.getLogger('FixEngine')

        db_path = self.config_manager.get('FIX', 'state_file', 'fix_state.db')
        self.message_store = MessageStoreFactory.get_message_store(
            'database',
            db_path,
            beginstring=self.version,
            sendercompid=self.sender,
            targetcompid=self.target
        )

        self.heartbeat_interval = int(self.config_manager.get('FIX', 'heartbeat_interval', '30'))
        self.lock = asyncio.Lock()
        
        self.test_request = TestRequest(self.send_message, self.config_manager, self.fixmsg)

        self.heartbeat = (HeartbeatBuilder()
                          .set_send_message_callback(self.send_message)
                          .set_config_manager(self.config_manager)
                          .set_heartbeat_interval(self.heartbeat_interval)
                          .set_state_machine(self.state_machine)
                          .set_fix_engine(self)
                          .build())
        
        self.session_id = f"{self.sender}-{self.target}-{self.host}:{self.port}"
        self.network = Acceptor(self.host, self.port, self.use_tls) if self.mode == 'acceptor' else Initiator(self.host, self.port, self.use_tls)

        self.event_notifier = EventNotifier()
        self.message_processor = MessageProcessor(self.message_store, self.state_machine, self.application, self)

        # Register Handlers
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
        self.scheduler_task = None

        self.retry_interval = int(self.config_manager.get('FIX', 'retry_interval', '5'))
        self.max_retries = int(self.config_manager.get('FIX', 'max_retries', '5'))
        self.retry_attempts = 0

        self.spec = FixSpec(self.spec_filename)
        self.codec = Codec(spec=self.spec, fragment_class=FixFragment)

    def fixmsg(self, *args, **kwargs):
        message = FixMessage(*args, **kwargs)
        message.codec = self.codec
        return message

    def create_message_with_repeating_group(self, msg_type: str, group_data: dict, **kwargs) -> FixMessage:
        initial_fields = {35: msg_type}
        initial_fields.update(kwargs)
        message = self.fixmsg(initial_fields)
        for num_in_group_tag, group_entries_data in group_data.items():
            if not isinstance(group_entries_data, list):
                self.logger.error(f"Data for group {num_in_group_tag} must be a list of dictionaries.")
                continue
            fragments_list = []
            for entry_data in group_entries_data:
                if not isinstance(entry_data, dict):
                    self.logger.error(f"Entry in group {num_in_group_tag} must be a dictionary. Got: {type(entry_data)}")
                    continue
                fragment = FixFragment(entry_data)
                fragments_list.append(fragment)
            message[num_in_group_tag] = fragments_list
        return message

    def on_state_change(self, state_name):
        self.logger.info(f"STATE CHANGE ({self.session_id}): {state_name}")
        if state_name == Active.name: # Use class attribute for name
            self.logger.info(f"Session {self.session_id} is now ACTIVE.")
            self.retry_attempts = 0
        elif state_name == Disconnected.name: # Use class attribute for name
            self.logger.info(f"Session {self.session_id} is DISCONNECTED.")
            if self.heartbeat and self.heartbeat.is_running():
                 self.logger.debug("Stopping heartbeat task due to disconnect.")
                 asyncio.create_task(self.heartbeat.stop())

    async def start(self):
        if not self.scheduler_task or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self.scheduler.run_scheduler())
            self.logger.info("Scheduler task started.")

        try:
            if self.mode == 'acceptor':
                self.logger.info(f"Acceptor starting on {self.host}:{self.port} for session {self.session_id}...")
                # Assuming 'listening_started' is an event handled by Disconnected state to move to a Listening state
                # Or, if your acceptor directly manages client sessions, this might not change the main engine state here.
                # For now, let's assume the main engine state doesn't change just by starting to listen.
                # self.state_machine.on_event('listening_started') # Requires Listening state and transition
                await self.network.start_accepting(self.handle_incoming_connection)
                self.logger.info(f"Acceptor {self.session_id} has stopped listening.")
            else: # Initiator
                self.logger.info(f"Initiator {self.session_id} starting to connect to {self.host}:{self.port}...")
                # Event for Disconnected -> Connecting
                self.state_machine.on_event('initiator_connect_attempt') 
                await self.network.connect() # Network layer connects
                self.logger.info(f"Initiator {self.session_id} TCP connected. Proceeding with FIX Logon.")
                # Event for Connecting -> LogonInProgress
                self.state_machine.on_event('connection_established') 
                await self.logon()
                await self.receive_message()
        except ConnectionRefusedError as e:
            self.logger.error(f"Connection refused for {self.session_id}: {e}")
            if self.mode == 'initiator':
                self.state_machine.on_event('connection_failed') # Connecting -> Disconnected
                await self.retry_connect()
        except Exception as e:
            self.logger.error(f"Failed to start or run FIX engine {self.session_id}: {e}", exc_info=True)
            if self.mode == 'initiator':
                self.state_machine.on_event('connection_failed') # Or a more generic error event
                await self.retry_connect()
        finally:
            self.logger.info(f"FIX Engine {self.session_id} start/run attempt concluded.")

    async def retry_connect(self):
        if self.mode == 'acceptor': return

        # Check should be against Reconnecting.name if that's the state during retries
        if self.state_machine.state.name != Active.name and self.retry_attempts < self.max_retries:
            self.retry_attempts += 1
             # Event for Disconnected/Error -> Reconnecting
            self.state_machine.on_event('initiate_reconnect')
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying connection for {self.session_id} in {backoff_time}s (Attempt {self.retry_attempts}/{self.max_retries}).")
            await asyncio.sleep(backoff_time)
            # The start() method will again try to connect, and its events should lead through Connecting -> LogonInProgress
            await self.start() 
        elif self.retry_attempts >= self.max_retries:
            self.logger.error(f"Max retries reached for {self.session_id}. Connection failed.")
            self.state_machine.on_event('reconnect_failed_max_retries') # Reconnecting -> Disconnected
        else:
            self.logger.info(f"Not retrying connection for {self.session_id}, current state: {self.state_machine.state.name}")


    async def handle_incoming_connection(self, reader, writer):
        client_address_info = writer.get_extra_info('peername')
        client_address = f"{client_address_info[0]}:{client_address_info[1]}" if client_address_info else "unknown client"
        self.logger.info(f"Accepted connection from {client_address} for session {self.session_id}.")

        # This part assumes the FixEngine instance handles one session.
        # If an acceptor handles multiple clients, each would need its own state context.
        # For now, we'll assume this engine instance is now dedicated to this client.
        try:
            await self.network.set_transport(reader, writer)
            # Event for Disconnected (or Listening) -> AwaitingLogon
            self.state_machine.on_event('client_accepted_awaiting_logon') 
            self.retry_attempts = 0 # Reset for this new session
            self.logger.info(f"Transport set for {client_address}. Waiting for Logon...")
            await self.receive_message()
        except ConnectionResetError:
            self.logger.warning(f"Connection reset by {client_address} during session {self.session_id}.")
        except asyncio.IncompleteReadError:
            self.logger.warning(f"Incomplete read from {client_address} (session {self.session_id}), connection closed prematurely.")
        except Exception as e:
            self.logger.error(f"Error handling connection from {client_address} (session {self.session_id}): {e}", exc_info=True)
        finally:
            self.logger.info(f"Cleaning up connection with {client_address} (session {self.session_id}).")
            if writer and not writer.is_closing():
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as e_close:
                    self.logger.error(f"Error during writer.wait_closed() for {client_address}: {e_close}")
            
            # This 'disconnect' event should be handled by AwaitingLogon, Active, etc. to go to Disconnected
            if self.state_machine.state.name != Disconnected.name:
                 self.logger.info(f"Setting state to DISCONNECTED after client {client_address} handling ended (main session: {self.session_id})")
                 self.state_machine.on_event('disconnect') 
            self.logger.info(f"Connection with {client_address} (session {self.session_id}) ended.")


    async def logon(self): # Initiator only
        if self.mode == 'acceptor':
            self.logger.critical("CRITICAL: Acceptor should not call FixEngine.logon().")
            return

        # Expects to be in LogonInProgress state
        if self.state_machine.state.name != LogonInProgress.name :
            self.logger.warning(f"Cannot initiate logon for {self.session_id}: State is {self.state_machine.state.name} (expected {LogonInProgress.name}). Aborting logon.")
            # If state is not LogonInProgress, it might be an issue, potentially disconnect.
            if self.state_machine.state.name != Disconnected.name: # Avoid loop if already disconnecting
                 await self.disconnect(graceful=False)
            return

        try:
            logon_message = self.fixmsg()
            reset_seq_num_flag_config = self.config_manager.get('FIX', 'reset_seq_num_on_logon', 'false').lower() == 'true'

            if reset_seq_num_flag_config:
                self.logger.info(f"ResetSeqNumFlag is true for {self.session_id}. Resetting sequence numbers to 1.")
                await self.reset_sequence_numbers()
                logon_message[141] = 'Y'
            else:
                logon_message[141] = 'N'

            logon_message.update({ 35: 'A', 108: self.heartbeat_interval })

            self.logger.info(f"Initiator {self.session_id} sending Logon (ResetSeqNumFlag={logon_message[141]}).")
            await self.send_message(logon_message) # This will add seq num, sender, target etc.
            # self.state_machine.on_event('logon_sent') # LogonInProgress -> LogonSent (if you add this state)
            self.logger.info(f"Initiator {self.session_id} Logon sent (SeqNum {logon_message.get(34)}). Waiting for response. Starting heartbeat mechanism.")
            if self.heartbeat: await self.heartbeat.start() # Start HB after sending Logon

        except Exception as e:
            self.logger.error(f"Failed to send Logon for {self.session_id}: {e}", exc_info=True)
            self.state_machine.on_event('logon_failed') # LogonInProgress -> Disconnected
            await self.disconnect(graceful=False) # Ensure cleanup


    async def send_message(self, message: FixMessage):
        # Allow sending Logon even if state is LogonInProgress (which is not DISCONNECTED)
        if self.state_machine.state.name == Disconnected.name and not \
           (message.get(35) == 'A' and self.mode == 'initiator' and self.state_machine.state.name == LogonInProgress.name): # This condition needs re-eval
            self.logger.warning(f"Cannot send message (type {message.get(35)}) for {self.session_id}: Session is DISCONNECTED.")
            return

        message[49] = self.sender
        message[56] = self.target
        message[52] = datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3]

        if 34 not in message: # SeqNum
            if message.get(35) == 'A' and message.get(141) == 'Y': # Logon with ResetSeqNumFlag
                message[34] = 1
            else:
                message[34] = self.message_store.get_next_outgoing_sequence_number()
        
        # For Logon messages, ensure sequence number is correctly handled by store *before* sending if reset
        if message.get(35) == 'A' and message.get(141) == 'Y':
            self.message_store.set_outgoing_sequence_number(1) # Explicitly set for store if reset
            message[34] = 1 # Ensure message has 1

        wire_message = message.to_wire(codec=self.codec)
        try:
            await self.network.send(wire_message)
            # Store message *after* successful send
            self.message_store.store_message(
                self.version, self.sender, self.target,
                message[34], # Use the actual sequence number from the message
                wire_message.decode(errors='replace')
            )
            if message.get(35) == 'A' and message.get(141) != 'Y': # If not a reset logon
                 self.message_store.increment_outgoing_sequence_number()


            self.logger.info(f"Sent ({self.session_id}): {message.get(35)} (SeqNum {message.get(34)})")
            if message.get(35) != '0' or self.logger.isEnabledFor(logging.DEBUG):
                 self.logger.debug(f"Sent Details ({self.session_id}): {message.to_wire(pretty=True)}")

        except ConnectionResetError as e:
            self.logger.error(f"ConnectionResetError for {self.session_id} while sending (type {message.get(35)}, seq {message.get(34)}): {e}")
            self.state_machine.on_event('disconnect') # Generic disconnect event
            await self.disconnect(graceful=False) # disconnect will ensure network layer is also handled
        except Exception as e:
            self.logger.error(f"Exception for {self.session_id} while sending (type {message.get(35)}, seq {message.get(34)}): {e}", exc_info=True)
            self.state_machine.on_event('disconnect') # Generic disconnect event
            await self.disconnect(graceful=False)


    async def receive_message(self):
        if not self.network.running:
            self.logger.warning(f"Network not running for {self.session_id} at start of receive_message. Ensuring disconnect state.")
            if self.state_machine.state.name != Disconnected.name:
                self.state_machine.on_event('disconnect') # Ensure state machine knows
                await self.disconnect(graceful=False) # Actual disconnect call
            return
        try:
            # self.handle_message will be called by network.receive for each chunk of data
            await self.network.receive(self.handle_message) 
        except Exception as e:
            self.logger.error(f"Unexpected error in FixEngine's receive_message for {self.session_id}: {e}", exc_info=True)
            if self.state_machine.state.name != Disconnected.name:
                 self.state_machine.on_event('disconnect')
                 await self.disconnect(graceful=False)
        finally:
            self.logger.info(f"FixEngine's receive_message loop for {self.session_id} has ended.")


    async def send_reject_message(self, ref_seq_num, ref_tag_id, session_reject_reason, text, ref_msg_type=None):
        self.logger.info(f"Preparing Session Reject for {self.session_id}: RefSeq={ref_seq_num}, RefTag={ref_tag_id}, Reason={session_reject_reason}, Text='{text}'")
        reject_msg = self.fixmsg({
            35: '3', 45: ref_seq_num, 58: text
        })
        if ref_tag_id: reject_msg[371] = ref_tag_id
        if ref_msg_type: reject_msg[372] = ref_msg_type
        if session_reject_reason is not None: reject_msg[373] = session_reject_reason
        await self.send_message(reject_msg)


    async def handle_message(self, data_bytes: bytes): # Expecting bytes from network.receive
        # FIX messages can be fragmented across TCP packets.
        # This handler needs to accumulate bytes until one or more complete FIX messages are formed.
        # For simplicity, this example assumes data_bytes might contain one or more full messages,
        # or a fragment. A proper FIX engine would have a more robust framing mechanism.
        # Using a simple SOH (0x01) split for this example, assuming standard FIX framing.
        
        # TODO: Implement proper FIX message framing (e.g., using a buffer and parsing BeginString, BodyLength)
        # This is a placeholder for basic splitting and will not handle all edge cases like SOH in values.
        
        data_str = data_bytes.decode(errors='replace') # Decode here, assuming one or more messages

        messages_str = data_str.split('\x018=') # Attempt to split by BeginString (SOH+8=)
        
        buffer = "" # In a real scenario, this buffer would be an instance variable
        
        for msg_part in messages_str:
            if not msg_part.strip():
                continue
            
            current_segment = ("8=" + msg_part if not buffer else msg_part)
            
            # Naive check for end of message (SOH for 10= CheckSum)
            # A robust parser would use BodyLength.
            if '\x0110=' in current_segment:
                full_fix_string = buffer + current_segment
                buffer = "" # Reset buffer for next message
                
                async with self.lock: # Process one fully formed message at a time
                    parsed_message = None
                    try:
                        # self.codec.decode expects a list of (tag, value) tuples or a string
                        # FixMessage.from_wire might be more direct if it handles raw strings
                        parsed_message = self.fixmsg().from_wire(full_fix_string, codec=self.codec)
                    except Exception as e:
                        self.logger.error(f"PARSE ERROR ({self.session_id}): '{full_fix_string[:150]}...' Error: {e}", exc_info=True)
                        # Consider sending a reject for unparseable message if possible
                        return # Stop processing this chunk

                    msg_type = parsed_message.get(35)
                    received_seq_num_str = parsed_message.get(34)
                    self.logger.info(f"Received ({self.session_id}): {msg_type} (Seq {received_seq_num_str})")
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Received Details ({self.session_id}): {parsed_message.to_wire(pretty=True)}")

                    if not received_seq_num_str or not received_seq_num_str.isdigit():
                        reason = f"Invalid or missing MsgSeqNum (34) in msg from {parsed_message.get(49, 'UNKNOWN')}: '{received_seq_num_str}'"
                        self.logger.error(reason)
                        await self.send_logout_message(text=reason)
                        self.state_machine.on_event('disconnect')
                        await self.disconnect(graceful=False)
                        return

                    received_seq_num = int(received_seq_num_str)

                    # Sequence number validation (excluding Logon, Logout, and SeqReset-GapFill)
                    if msg_type not in ['A', '5'] and not (msg_type == '4' and parsed_message.get(123) == 'N'): # 123=Y for GapFill
                        expected_seq_num = self.message_store.get_next_incoming_sequence_number()

                        if received_seq_num < expected_seq_num:
                            poss_dup_flag = parsed_message.get(43) # Tag 43 PossDupFlag
                            if poss_dup_flag == 'Y':
                                self.logger.info(f"PossDup {msg_type} (Seq {received_seq_num}) rcvd for {self.session_id} (expected {expected_seq_num}). App layer should handle.")
                            else:
                                text = f"MsgSeqNum too low, expected {expected_seq_num} but received {received_seq_num}"
                                self.logger.error(f"{text} for {self.session_id}. Not PossDup. Sending Logout.")
                                await self.send_logout_message(text=text)
                                self.state_machine.on_event('disconnect')
                                await self.disconnect(graceful=False)
                                return
                        elif received_seq_num > expected_seq_num:
                            self.logger.warning(f"MsgSeqNum TOO HIGH (Gap) for {self.session_id}. Expected: {expected_seq_num}, Rcvd: {received_seq_num}. Sending Resend Request.")
                            resend_req = self.fixmsg({ 35: '2', 7: expected_seq_num, 16: 0 }) # 16=EndSeqNo (0 for all)
                            await self.send_message(resend_req)
                            return # Do not process this message further, wait for resend

                    # Store message before processing (especially before incrementing seq num)
                    self.message_store.store_message(
                        self.version, parsed_message.get(49), parsed_message.get(56),
                        received_seq_num,
                        full_fix_string # Store the raw string that was parsed
                    )

                    # Increment incoming sequence number *after* validation and *before* app processing for most messages
                    # Logon (A) seq num handling is special (can be 1 with ResetSeqNumFlag)
                    # Logout (5) processing might happen even if seq num is off, then disconnect
                    # SequenceReset-GapFill (4 with 123=Y) sets the next expected, doesn't just increment.
                    if msg_type != 'A' and not (msg_type == '4' and parsed_message.get(123) == 'Y'): # 123=Y is GapFill
                        self.message_store.set_incoming_sequence_number(received_seq_num + 1)


                    # Process the message using registered handlers
                    await self.message_processor.process_message(parsed_message)
            else: # Accumulate partial message
                buffer += current_segment
                if buffer: # Log if we are buffering
                    self.logger.debug(f"Buffering partial FIX message segment: {buffer[:100]}...")


    async def disconnect(self, graceful=True):
        current_state_name = self.state_machine.state.name
        self.logger.info(f"Disconnect requested for {self.session_id}. Graceful: {graceful}. Current state: {current_state_name}.")

        if current_state_name == Disconnected.name and (not self.network or not self.network.running):
            self.logger.info(f"Session {self.session_id} already disconnected and network not running.")
            return
        
        # Use a specific event if a graceful logout is being initiated from Active state
        if graceful and current_state_name == Active.name:
            self.state_machine.on_event('logout_initiated') # Active -> LogoutInProgress
            try:
                self.logger.info(f"Attempting graceful logout for {self.session_id}.")
                await self.send_logout_message() # This might also call disconnect if it fails
            except Exception as e_logout:
                self.logger.error(f"Error sending logout for {self.session_id} during graceful disconnect: {e_logout}")
                # If send_logout_message fails, it might have already called disconnect.
                # Ensure we still proceed with network disconnect.
        else:
            # For non-graceful or if not Active, trigger a general disconnect event
            # This allows states like LogonInProgress, AwaitingLogon etc. to go to Disconnected
            if current_state_name != Disconnected.name:
                 self.state_machine.on_event('disconnect')


        if self.network: # self.network should always exist
            self.logger.debug(f"Disconnecting network layer for {self.session_id}.")
            await self.network.disconnect() # This sets network.running to False

        if self.heartbeat and self.heartbeat.is_running():
            self.logger.debug(f"Stopping heartbeat for {self.session_id}.")
            await self.heartbeat.stop()

        if self.scheduler_task and not self.scheduler_task.done():
            self.logger.debug(f"Cancelling scheduler task for {self.session_id}.")
            self.scheduler_task.cancel()
            try: await self.scheduler_task
            except asyncio.CancelledError: self.logger.info(f"Scheduler task for {self.session_id} cancelled.")
            self.scheduler_task = None


        if self.message_store and hasattr(self.message_store, 'close'):
            self.logger.debug(f"Closing message store for {self.session_id}.")
            self.message_store.close()

        self.retry_attempts = 0 # Reset retries on disconnect
        
        # Final check: ensure state machine is in Disconnected state
        if self.state_machine.state.name != Disconnected.name:
            self.logger.warning(f"State was {self.state_machine.state.name} after disconnect ops. Forcing to {Disconnected.name}.")
            # This direct state set is unusual but ensures cleanup. Prefer event-driven.
            # self.state_machine.state = Disconnected()
            # self.state_machine.notify_subscribers()
            # Better: ensure the 'disconnect' event is robustly handled by all states to reach Disconnected
            self.state_machine.on_event('force_disconnect') # A new event that all states must map to Disconnected

        self.logger.info(f"FIX Engine {self.session_id} disconnected operations complete.")


    async def reset_sequence_numbers(self):
        self.logger.info(f"Resetting sequence numbers to 1 for {self.session_id} (both inbound and outbound).")
        if self.message_store:
            self.message_store.reset_sequence_numbers()

    async def set_inbound_sequence_number(self, seq_num: int):
        self.logger.info(f"Externally setting inbound sequence for {self.session_id} to {seq_num}.")
        if self.message_store:
            self.message_store.set_incoming_sequence_number(seq_num)

    async def set_outbound_sequence_number(self, seq_num: int):
        self.logger.info(f"Externally setting outbound sequence for {self.session_id} to {seq_num}.")
        if self.message_store:
            self.message_store.set_outgoing_sequence_number(seq_num)


    async def send_logout_message(self, text: str = "Operator requested logout"):
        current_state_name = self.state_machine.state.name
        
        if current_state_name == Disconnected.name:
            self.logger.info(f"Cannot send Logout for {self.session_id}: Already disconnected.")
            return
        
        # If logout is already in progress, don't send another one.
        if current_state_name == LogoutInProgress.name:
            self.logger.info(f"Logout already in progress for {self.session_id}. New logout request ignored.")
            return

        self.logger.info(f"Sending Logout for {self.session_id}. Text: '{text}'")
        logout_msg = self.fixmsg({ 35: '5', 58: text })

        try:
            # Transition to LogoutInProgress if not already disconnecting or in that state
            if current_state_name == Active.name:
                 self.state_machine.on_event('logout_initiated') # Active -> LogoutInProgress
            # If in other states (e.g. AwaitingLogon, LogonInProgress) and sending logout,
            # the subsequent disconnect will handle state.

            await self.send_message(logout_msg) # send_message handles DISCONNECTED state check
            self.logger.info(f"Successfully sent Logout (Seq {logout_msg.get(34)}) for {self.session_id}.")
            # After sending logout, expect peer to also send logout then disconnect, or just disconnect.
            # The engine will transition to DISCONNECTED when the peer disconnects or if LogoutHandler processes peer's Logout.
        except Exception as e:
            self.logger.error(f"Failed to send Logout for {self.session_id}: {e}", exc_info=True)
            # If sending logout fails, force a non-graceful disconnect
            if current_state_name != Disconnected.name:
                 self.state_machine.on_event('disconnect') # Generic disconnect
                 await self.disconnect(graceful=False)
        # Do not call disconnect here unconditionally; wait for peer's logout or timeout.
        # The disconnect() method is the main one to tear down the connection.
        # If this send_logout_message is part of a graceful disconnect, disconnect() will be called after.
