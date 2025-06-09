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
from pyfixmsg.fixmessage import FixMessage, FixFragment # Ensure FixFragment is imported
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec
# FixFragment was already imported via `from pyfixmsg.fixmessage import FixMessage, FixFragment`
# but if it wasn't, it would need to be:
# from pyfixmsg.fixmessage import FixFragment


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

        self.logger = logging.getLogger('FixEngine')
        # self.logger.setLevel(logging.DEBUG) # Set level based on config or globally

        db_path = self.config_manager.get('FIX', 'state_file', 'fix_state.db')
        # Pass session identifiers directly to the factory
        self.message_store = MessageStoreFactory.get_message_store(
            'database',
            db_path,
            beginstring=self.version,
            sendercompid=self.sender,
            targetcompid=self.target
        )

        self.heartbeat_interval = int(self.config_manager.get('FIX', 'heartbeat_interval', '30'))
        self.lock = asyncio.Lock()
        self.heartbeat = (HeartbeatBuilder()
                          .set_send_message_callback(self.send_message)
                          .set_config_manager(self.config_manager)
                          .set_heartbeat_interval(self.heartbeat_interval)
                          .set_state_machine(self.state_machine)
                          .set_fix_engine(self)
                          .build())
        self.test_request = TestRequest(self.send_message, self.config_manager, self.fixmsg) # Pass self.fixmsg
        self.session_id = f"{self.sender}-{self.target}-{self.host}:{self.port}" # More unique session ID
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
        self.scheduler_task = None # Will be created in connect or run

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
        """
        Creates a FIX message with specified repeating groups, using the engine's codec.

        Args:
            msg_type (str): The FIX message type (e.g., 'D' for NewOrderSingle).
            group_data (dict): Data for repeating groups.
                               Keys are the 'NumInGroup' tag as integers (e.g., 73 for NoOrders, 268 for NoMDEntries).
                               Values are lists of dictionaries, where each dictionary represents a group entry
                               (a FixFragment), with keys as integer tags and values as the field values.
            **kwargs: Additional top-level fields for the message (e.g., ClOrdID='123').

        Returns:
            FixMessage: A new FIX message with the specified type and repeating groups populated.
        
        Example:
            md_entries_data = [
                {279: 0, 270: 100.0, 271: 10}, # MDUpdateAction=NEW, MDPrice=100.0, MDEntrySize=10
                {279: 1, 270: 101.0, 271: 20}  # MDUpdateAction=CHANGE, MDPrice=101.0, MDEntrySize=20
            ]
            message = engine.create_message_with_repeating_group(
                msg_type='X',  # MarketDataSnapshotFullRefresh
                group_data={
                    268: md_entries_data # 268 is NoMDEntries
                },
                MDReqID='req123' # A top-level field
            )
        """
        # Initialize the message with top-level fields and the MsgType
        initial_fields = {35: msg_type}
        initial_fields.update(kwargs) # Add any other top-level fields
        message = self.fixmsg(initial_fields) # Uses engine's codec

        for num_in_group_tag, group_entries_data in group_data.items():
            if not isinstance(group_entries_data, list):
                self.logger.error(f"Data for group {num_in_group_tag} must be a list of dictionaries.")
                # Or raise an error: raise ValueError(f"Data for group {num_in_group_tag} must be a list.")
                continue

            fragments_list = []
            for entry_data in group_entries_data:
                if not isinstance(entry_data, dict):
                    self.logger.error(f"Entry in group {num_in_group_tag} must be a dictionary. Got: {type(entry_data)}")
                    # Or raise an error
                    continue
                # Create a FixFragment from the dictionary of fields for this group entry
                fragment = FixFragment(entry_data)
                fragments_list.append(fragment)
            
            # Assign the list of FixFragment objects to the message using the NumInGroup tag
            message[num_in_group_tag] = fragments_list
            self.logger.debug(f"Added repeating group for tag {num_in_group_tag} with {len(fragments_list)} entries.")

        return message

    def on_state_change(self, state_name):
        self.logger.info(f"STATE CHANGE ({self.session_id}): {state_name}")
        if state_name == 'ACTIVE':
            self.logger.info(f"Session {self.session_id} is now ACTIVE.")
            self.retry_attempts = 0 # Reset retries on successful connection
        elif state_name == 'DISCONNECTED':
            self.logger.info(f"Session {self.session_id} is DISCONNECTED.")
            if self.heartbeat and self.heartbeat.is_running():
                 self.logger.debug("Stopping heartbeat task due to disconnect.")
                 asyncio.create_task(self.heartbeat.stop()) # Ensure heartbeat stops


    async def start(self): # Renamed from connect to start for clarity, or keep connect
        """Starts the FIX engine (listens as acceptor or connects as initiator)."""
        if not self.scheduler_task or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self.scheduler.run_scheduler())
            self.logger.info("Scheduler task started.")

        try:
            if self.mode == 'acceptor':
                self.logger.info(f"Acceptor starting on {self.host}:{self.port} for session {self.session_id}...")
                self.state_machine.on_event('listening')
                await self.network.start_accepting(self.handle_incoming_connection)
                self.logger.info(f"Acceptor {self.session_id} has stopped listening.")
            else: # Initiator mode
                self.logger.info(f"Initiator {self.session_id} starting to connect to {self.host}:{self.port}...")
                self.state_machine.on_event('connecting')
                await self.network.connect()
                self.logger.info(f"Initiator {self.session_id} TCP connected. Proceeding with FIX Logon.")
                self.state_machine.on_event('logon_initiated')
                await self.logon()
                await self.receive_message()
        except ConnectionRefusedError as e:
            self.logger.error(f"Connection refused for {self.session_id}: {e}")
            if self.mode == 'initiator':
                await self.retry_connect()
        except Exception as e:
            self.logger.error(f"Failed to start or run FIX engine {self.session_id}: {e}", exc_info=True)
            if self.mode == 'initiator':
                await self.retry_connect()
        finally:
            self.logger.info(f"FIX Engine {self.session_id} start/run attempt concluded.")
            # Disconnect might be called if an unhandled exception bubbles up or loop ends

    async def retry_connect(self):
        if self.mode == 'acceptor': return

        if self.state_machine.state.name != 'ACTIVE' and self.retry_attempts < self.max_retries:
            self.retry_attempts += 1
            self.state_machine.on_event('reconnecting')
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying connection for {self.session_id} in {backoff_time}s (Attempt {self.retry_attempts}/{self.max_retries}).")
            await asyncio.sleep(backoff_time)
            await self.start() # Retry the whole start sequence
        elif self.retry_attempts >= self.max_retries:
            self.logger.error(f"Max retries reached for {self.session_id}. Connection failed.")
            self.state_machine.on_event('disconnect')
        else:
            self.logger.info(f"Not retrying connection for {self.session_id}, current state: {self.state_machine.state.name}")


    async def handle_incoming_connection(self, reader, writer):
        client_address_info = writer.get_extra_info('peername')
        client_address = f"{client_address_info[0]}:{client_address_info[1]}" if client_address_info else "unknown client"
        self.logger.info(f"Accepted connection from {client_address} for session {self.session_id}.")

        try:
            await self.network.set_transport(reader, writer)
            self.state_machine.on_event('tcp_connected')
            self.retry_attempts = 0 # Reset retries for this new connection attempt by client
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

            if self.state_machine.state.name != 'DISCONNECTED':
                 self.logger.info(f"Setting state to DISCONNECTED for session with {client_address} (main session: {self.session_id})")
                 self.state_machine.on_event('disconnect')
            self.logger.info(f"Connection with {client_address} (session {self.session_id}) ended.")


    async def logon(self):
        if self.mode == 'acceptor':
            self.logger.critical("CRITICAL: Acceptor should not call FixEngine.logon().")
            return

        if self.state_machine.state.name not in ['LOGON_INITIATED', 'RECONNECTING']: # Allow logon after reconnecting state
            self.logger.warning(f"Cannot initiate logon for {self.session_id}: State is {self.state_machine.state.name}. Aborting logon.")
            return

        try:
            logon_message = self.fixmsg()
            reset_seq_num_flag_config = self.config_manager.get('FIX', 'reset_seq_num_on_logon', 'false').lower() == 'true'

            if reset_seq_num_flag_config:
                self.logger.info(f"ResetSeqNumFlag is true for {self.session_id}. Resetting sequence numbers to 1.")
                await self.reset_sequence_numbers() # Resets store's seq nums to 1
                logon_message[141] = 'Y' # ResetSeqNumFlag=Y
                # MsgSeqNum will be set to 1 by send_message due to this flag on Logon
            else:
                logon_message[141] = 'N' # ResetSeqNumFlag=N

            logon_message.update({ 35: 'A', 108: self.heartbeat_interval })
            # SenderCompID, TargetCompID, MsgSeqNum, SendingTime handled by send_message

            self.logger.info(f"Initiator {self.session_id} sending Logon (ResetSeqNumFlag={logon_message[141]}).")
            await self.send_message(logon_message)
            self.logger.info(f"Initiator {self.session_id} Logon sent (SeqNum {logon_message.get(34)}). Starting heartbeat mechanism.")
            if self.heartbeat: await self.heartbeat.start()

        except Exception as e:
            self.logger.error(f"Failed to send Logon for {self.session_id}: {e}", exc_info=True)
            self.state_machine.on_event('logon_failed')
            await self.disconnect(graceful=False)


    async def send_message(self, message: FixMessage):
        if self.state_machine.state.name == 'DISCONNECTED' and not (message.get(35) == 'A' and self.mode == 'initiator'): # Allow sending Logon even if state is briefly disconnected during startup
            self.logger.warning(f"Cannot send message (type {message.get(35)}) for {self.session_id}: Session is DISCONNECTED.")
            return

        message[49] = self.sender
        message[56] = self.target
        message[52] = datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3]

        if 34 not in message:
            if message.get(35) == 'A' and message.get(141) == 'Y':
                message[34] = 1 # MsgSeqNum must be 1 if ResetSeqNumFlag=Y on Logon
            else:
                message[34] = self.message_store.get_next_outgoing_sequence_number()

        wire_message = message.to_wire(codec=self.codec)
        try:
            await self.network.send(wire_message)
            self.message_store.store_message(
                self.version, self.sender, self.target,
                message[34],
                wire_message.decode(errors='replace')
            )
            self.logger.info(f"Sent ({self.session_id}): {message.get(35)} (SeqNum {message[34]})")
            if message.get(35) != '0' or self.logger.isEnabledFor(logging.DEBUG):
                 self.logger.debug(f"Sent Details ({self.session_id}): {message.to_wire(pretty=True)}")

        except ConnectionResetError as e:
            self.logger.error(f"ConnectionResetError for {self.session_id} while sending (type {message.get(35)}, seq {message.get(34)}): {e}")
            await self.disconnect(graceful=False)
        except Exception as e:
            self.logger.error(f"Exception for {self.session_id} while sending (type {message.get(35)}, seq {message.get(34)}): {e}", exc_info=True)
            await self.disconnect(graceful=False)


    async def receive_message(self):
        if not self.network.running:
            self.logger.warning(f"Network not running for {self.session_id} at start of receive_message. Disconnecting.")
            if self.state_machine.state.name != 'DISCONNECTED':
                await self.disconnect(graceful=False)
            return
        try:
            await self.network.receive(self.handle_message)
        except Exception as e: # Catch-all, as network.receive should handle its specific errors
            self.logger.error(f"Unexpected error in FixEngine's receive_message for {self.session_id}: {e}", exc_info=True)
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
        self.logger.info(f"Sent Session Reject for {self.session_id} (RefSeq {ref_seq_num}).")


    async def handle_message(self, data_str: str):
        async with self.lock:
            parsed_message = None
            try:
                parsed_message = self.fixmsg().from_wire(data_str, codec=self.codec)
            except Exception as e:
                self.logger.error(f"PARSE ERROR ({self.session_id}): '{data_str[:150]}...' Error: {e}", exc_info=True)
                return

            msg_type = parsed_message.get(35)
            received_seq_num_str = parsed_message.get(34)
            self.logger.info(f"Received ({self.session_id}): {msg_type} (Seq {received_seq_num_str})")
            if self.logger.isEnabledFor(logging.DEBUG): # Avoid costly pretty print if not needed
                 self.logger.debug(f"Received Details ({self.session_id}): {parsed_message.to_wire(pretty=True)}")

            if not received_seq_num_str or not received_seq_num_str.isdigit():
                reason = f"Invalid or missing MsgSeqNum (34) in msg from {parsed_message.get(49, 'UNKNOWN')}: '{received_seq_num_str}'"
                self.logger.error(reason)
                await self.send_logout_message(text=reason)
                await self.disconnect(graceful=False)
                return

            received_seq_num = int(received_seq_num_str)

            # --- Sequence Number Processing ---
            if msg_type not in ['A', '5'] and not (msg_type == '4' and parsed_message.get(123) == 'N'): # Exclude Logon, Logout, SeqReset-Reset
                expected_seq_num = self.message_store.get_next_incoming_sequence_number()

                if received_seq_num < expected_seq_num:
                    poss_dup_flag = parsed_message.get(43, 'N')
                    if poss_dup_flag == 'Y':
                        self.logger.info(f"PossDup {msg_type} (Seq {received_seq_num}) rcvd for {self.session_id} (expected {expected_seq_num}). App layer should handle.")
                        # No automatic logout for PossDup=Y with lower seq num. Pass to app.
                    else: # Not PossDup, but seq num is too low. This is a serious error.
                        self.logger.error(f"MsgSeqNum TOO LOW for {self.session_id}. Expected: {expected_seq_num}, Rcvd: {received_seq_num}. Not PossDup. Disconnecting.")
                        text = f"MsgSeqNum too low, expected {expected_seq_num} but received {received_seq_num}"
                        await self.send_logout_message(text=text)
                        await self.disconnect(graceful=False)
                        return

                elif received_seq_num > expected_seq_num:
                    self.logger.warning(f"MsgSeqNum TOO HIGH (Gap) for {self.session_id}. Expected: {expected_seq_num}, Rcvd: {received_seq_num}. Sending Resend Request.")
                    resend_req = self.fixmsg({
                        35: '2', 7: expected_seq_num, 16: 0 # EndSeqNo=0 for all subsequent
                    })
                    await self.send_message(resend_req)
                    return # DO NOT process the gapped message. Wait for resend.

            # Store message (raw string)
            self.message_store.store_message(
                self.version, parsed_message.get(49), parsed_message.get(56), # Use CompIDs from message for storage key
                received_seq_num,
                data_str
            )

            # Increment incoming sequence number for NON-Logon and NON-SequenceReset-Reset messages
            # LogonHandler will call increment_incoming_sequence_number itself after validating Logon.
            # SequenceResetHandler (for Reset mode) handles its own sequence update.
            if msg_type != 'A' and not (msg_type == '4' and parsed_message.get(123) == 'N'):
                self.message_store.increment_incoming_sequence_number()

            await self.message_processor.process_message(parsed_message)

    async def disconnect(self, graceful=True):
        current_state = self.state_machine.state.name
        self.logger.info(f"Disconnect requested for {self.session_id}. Graceful: {graceful}. Current state: {current_state}.")

        if current_state == 'DISCONNECTED' and (not self.network or not self.network.running):
            self.logger.info(f"Session {self.session_id} already disconnected.")
            return

        self.state_machine.on_event('disconnect_initiated')

        if graceful and current_state == 'ACTIVE':
            try:
                self.logger.info(f"Attempting graceful logout for {self.session_id}.")
                await self.send_logout_message()
            except Exception as e_logout:
                self.logger.error(f"Error sending logout for {self.session_id} during graceful disconnect: {e_logout}")

        if self.network:
            self.logger.debug(f"Disconnecting network layer for {self.session_id}.")
            await self.network.disconnect()

        if self.heartbeat and self.heartbeat.is_running():
            self.logger.debug(f"Stopping heartbeat for {self.session_id}.")
            await self.heartbeat.stop()

        if self.scheduler_task and not self.scheduler_task.done():
            self.logger.debug(f"Cancelling scheduler task for {self.session_id}.")
            self.scheduler_task.cancel()
            try: await self.scheduler_task
            except asyncio.CancelledError: self.logger.info(f"Scheduler task for {self.session_id} cancelled.")

        if self.message_store and hasattr(self.message_store, 'close'):
            self.logger.debug(f"Closing message store for {self.session_id}.")
            self.message_store.close() # Close the database connection

        self.retry_attempts = 0
        if current_state != 'DISCONNECTED':
            self.state_machine.on_event('disconnect')
        self.logger.info(f"FIX Engine {self.session_id} disconnected.")


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
        current_state = self.state_machine.state.name
        if current_state == 'DISCONNECTED' and (not self.network or not self.network.running):
            self.logger.info(f"Cannot send Logout for {self.session_id}: Already disconnected.")
            return

        if current_state == 'LOGOUT_IN_PROGRESS': # Avoid re-sending if already in process
            self.logger.info(f"Cannot send Logout for {self.session_id}: Logout already in progress.")
            return

        self.logger.info(f"Sending Logout for {self.session_id}. Text: '{text}'")
        logout_msg = self.fixmsg({ 35: '5', 58: text })

        try:
            if current_state not in ['DISCONNECTED', 'LOGOUT_IN_PROGRESS']:
                 self.state_machine.on_event('logout_sent')

            await self.send_message(logout_msg) # This will set CompIDs, SeqNum, Time
            self.logger.info(f"Successfully sent Logout (Seq {logout_msg.get(34)}) for {self.session_id}.")
        except Exception as e:
            self.logger.error(f"Failed to send Logout for {self.session_id}: {e}", exc_info=True)
        finally:
            # After attempting to send Logout, always proceed to full disconnect.
            # disconnect() will handle ensuring the state becomes DISCONNECTED.
            # The 'graceful=False' here ensures TCP is torn down quickly after our logout attempt.
            if current_state != 'DISCONNECTED': # Check current_state again, as send_message might have disconnected on failure
                 await self.disconnect(graceful=False)
