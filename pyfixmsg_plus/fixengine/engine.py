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
        self.logger.setLevel(logging.DEBUG)
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
        self.last_heartbeat_time = None
        self.missed_heartbeats = 0
        self.session_id = f"{self.host}:{self.port}"
        self.network = Acceptor(self.host, self.port, self.use_tls) if self.mode == 'acceptor' else Initiator(self.host, self.port, self.use_tls)
        
        self.event_notifier = EventNotifier()
        # Pass self (FixEngine instance) to MessageProcessor and then to handlers if they need to call engine methods like send_message or access engine state.
        self.message_processor = MessageProcessor(self.message_store, self.state_machine, self.application, self) 
        
        # Register message handlers, potentially passing self (FixEngine) if handlers need it
        # Example: LogonHandler(self.message_store, self.state_machine, self.application, self)
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
        message = FixMessage(*args, **kwargs)
        message.codec = self.codec
        return message

    def on_state_change(self, state_name):
        self.logger.info(f"State changed to: {state_name}")
        if state_name == 'LOGON_IN_PROGRESS':
            self.logger.debug("Logon process has started.")
        elif state_name == 'ACTIVE':
            self.logger.debug("Connection is now active. Starting heartbeat.")
            # Ensure heartbeat is started only once when session becomes active
            # The LogonHandler (for acceptor) or FixEngine.logon (for initiator) should manage this.
            # This is a good place to log it, but the actual start might be elsewhere.
        elif state_name == 'DISCONNECTED':
            self.logger.debug("Connection has been disconnected. Stopping heartbeat.")
            if self.heartbeat.is_running():
                 asyncio.create_task(self.heartbeat.stop())


    async def connect(self):
        try:
            # self.state_machine.on_event('connect') # This might be too generic.
                                                 # Specific states like 'CONNECTING' might be better.
            if self.mode == 'acceptor':
                self.logger.info("Starting in acceptor mode, waiting for incoming connections...")
                # The start_accepting method blocks until the server is closed.
                # It passes self.handle_incoming_connection as a callback for each new client.
                await self.network.start_accepting(self.handle_incoming_connection)
            else: # Initiator mode
                self.state_machine.on_event('connect') # Initiator is actively connecting
                self.logger.info("Initiator connecting to FIX server...")
                await self.network.connect()
                # self.network.running should be True now
                self.logger.info("Initiator connected to FIX server. Proceeding with logon.")
                self.state_machine.on_event('logon') # Transition to LogonInProgress
                await self.logon() # Initiator sends Logon
                await self.receive_message() # Start receiving messages after logon initiated
        except ConnectionRefusedError as e:
            self.logger.error(f"Failed to connect (connection refused): {e}")
            await self.retry_connect()
        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            await self.retry_connect()

    async def retry_connect(self): # Primarily for initiator
        if self.mode == 'acceptor':
            self.logger.info("Acceptor mode: Will continue listening or restart listening via main loop if necessary.")
            return

        if self.retry_attempts < self.max_retries:
            self.retry_attempts += 1
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying connection in {backoff_time} seconds (Attempt {self.retry_attempts}/{self.max_retries})...")
            await asyncio.sleep(backoff_time)
            await self.connect() # Retry the whole connect sequence
        else:
            self.logger.error("Max retries reached. Connection failed.")
            self.state_machine.on_event('disconnect') # Ensure state is Disconnected

    async def handle_incoming_connection(self, reader, writer):
        # This method is called by Acceptor's start_server for each new client.
        client_address = None
        try:
            client_address = writer.get_extra_info('peername')
            self.logger.info(f"Accepted incoming connection from {client_address}.")
            
            # Set transport for this specific connection.
            # This implies FixEngine handles one session at a time, or network.set_transport is very clever.
            # For now, assume one session.
            await self.network.set_transport(reader, writer)
            # self.network.running should now be True for this connection via set_transport.

            self.logger.info(f"Waiting for Logon from {client_address}...")
            # The receive_message loop will handle the incoming Logon via MessageProcessor -> LogonHandler
            # LogonHandler (for acceptor) should then send its own Logon and set state to Active.
            await self.receive_message()

        except ConnectionResetError:
            self.logger.warning(f"Connection reset by {client_address if client_address else 'unknown client'}.")
        except asyncio.IncompleteReadError:
            self.logger.warning(f"Incomplete read from {client_address if client_address else 'unknown client'}, connection closed prematurely.")
        except Exception as e:
            self.logger.error(f"Error handling incoming connection from {client_address if client_address else 'unknown client'}: {e}", exc_info=True)
        finally:
            self.logger.info(f"Cleaning up connection with {client_address if client_address else 'unknown client'}.")
            if writer and not writer.is_closing():
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as e_close:
                    self.logger.error(f"Error during writer.wait_closed() for {client_address}: {e_close}")
            
            # Reset state for this session. If FixEngine is single-session, this makes sense.
            # If it can handle multiple, this state management needs to be per-session.
            if self.state_machine.state.name != 'DISCONNECTED':
                 self.state_machine.on_event('disconnect')
            self.logger.info(f"Connection with {client_address if client_address else 'unknown client'} ended.")


    async def logon(self): # This is primarily for the INITIATOR to send its Logon
        if self.mode == 'acceptor':
            self.logger.error("Acceptor should not call FixEngine.logon() directly. Logon is sent by LogonHandler in response to initiator.")
            return

        # Check state: should be LOGON_IN_PROGRESS (set after connect() for initiator)
        if self.state_machine.state.name != 'LOGON_IN_PROGRESS':
            self.logger.error(f"Cannot initiate logon: State is {self.state_machine.state.name}, expected LOGON_IN_PROGRESS.")
            # It might be already 'ACTIVE' if retry_logon was called after a successful logon,
            # or 'DISCONNECTED' if connection failed before this.
            # Consider if 'ACTIVE' should also prevent re-sending logon, or if this is part of a recovery.
            if self.state_machine.state.name != 'ACTIVE': # Allow retry if active for some reason? Usually no.
                 return

        try:
            self.logger.info("Initiator sending Logon message...")
            logon_message = self.fixmsg()
            logon_message.update({
                35: 'A',  # MsgType
                49: self.sender,  # SenderCompID
                56: self.target,  # TargetCompID
                34: self.message_store.get_next_outgoing_sequence_number(),  # MsgSeqNum
                108: self.heartbeat_interval # HeartBtInt
            })
            # Potentially add other fields like EncryptMethod(98), DefaultApplVerID(1137) if needed
            await self.send_message(logon_message)
            self.logger.info("Initiator Logon message sent. Starting heartbeat timer.")
            await self.heartbeat.start() # Start heartbeat mechanism (sending and monitoring)
            # State remains LOGON_IN_PROGRESS until Logon response from acceptor moves it to ACTIVE.
        except Exception as e:
            self.logger.error(f"Failed to send Logon message: {e}")
            # State might need to go to DISCONNECTED or a retry state.
            self.state_machine.on_event('disconnect') # Or a more specific error state
            await self.retry_logon() # This retry logic might need refinement

    async def retry_logon(self): # For initiator if initial logon send fails or times out
        if self.mode == 'acceptor': return

        if self.retry_attempts < self.max_retries:
            # self.state_machine.on_event('reconnect') # This event might imply full TCP reconnect.
                                                    # 'logon_retry' might be more appropriate.
            self.retry_attempts += 1
            backoff_time = self.retry_interval * (2 ** (self.retry_attempts - 1))
            self.logger.info(f"Retrying logon in {backoff_time} seconds (Attempt {self.retry_attempts}/{self.max_retries})...")
            await asyncio.sleep(backoff_time)
            
            # Before retrying logon, ensure connection is still valid or re-establish.
            if not self.network.running: # or check a more specific connection status
                self.logger.info("Connection lost before logon retry. Attempting to reconnect.")
                # This should ideally go through the full connect and logon process again.
                # For simplicity, we might just try to logon again if state allows.
                # This part is tricky: retry_connect vs retry_logon.
                # If logon failed due to network issue, retry_connect is better.
                # If it failed due to FIX level issue (e.g. immediate reject to our logon), then just retrying logon might not help.
                await self.connect() #This will attempt full connection and then logon
            else:
                 self.state_machine.on_event('logon') # Set state for logon attempt
                 await self.logon()
        else:
            self.logger.error("Max retries reached for logon. Logon failed.")
            self.state_machine.on_event('disconnect')


    async def send_message(self, message: FixMessage):
        # Ensure critical fields are set if not already present
        message[52] = datetime.now(timezone.utc).strftime('%Y%m%d-%H:%M:%S.%f')[:-3] # SendingTime
        if 34 not in message: # MsgSeqNum
            message[34] = self.message_store.get_next_outgoing_sequence_number()
        
        # BodyLength (9) and Checksum (10) are typically handled by to_wire()
        
        wire_message = message.to_wire(codec=self.codec)
        await self.network.send(wire_message) # network.send expects bytes
        self.message_store.store_message(self.version, self.sender, self.target, message[34], wire_message.decode(errors='replace')) # Store the string representation for easier retrieval if needed
        self.logger.info(f"Sent: {message.get(35)} (SeqNum {message[34]})")


    async def receive_message(self):
        # This method now relies on network.receive to manage the actual read loop
        # and call self.handle_message for each complete FIX message string.
        if not self.network.running:
            self.logger.warning("Network is not running at the start of receive_message. Cannot receive.")
            # This might happen if set_transport (for acceptor) or connect (for initiator) failed to set network.running.
            # Or if disconnect was called.
            return

        try:
            # self.network.receive takes a handler (self.handle_message)
            # and will call it with decoded string data.
            await self.network.receive(self.handle_message)
        except ConnectionResetError:
            self.logger.warning("Receive loop terminated: Connection reset.")
            await self.disconnect(graceful=False)
        except asyncio.IncompleteReadError:
            self.logger.warning("Receive loop terminated: Incomplete read, connection closed.")
            await self.disconnect(graceful=False)
        except Exception as e:
            self.logger.error(f"Critical error in receive_message infrastructure: {e}", exc_info=True)
            await self.disconnect(graceful=False)
        finally:
            self.logger.info("Receive message loop has ended.")
            # Ensure state reflects disconnection if not already handled
            if self.state_machine.state.name != 'DISCONNECTED':
                self.state_machine.on_event('disconnect')


    async def send_reject_message(self, ref_seq_num, ref_tag_id, session_reject_reason, text):
        reject_message = self.fixmsg()
        reject_message.update({
            35: '3',  # MsgType: Reject
            49: self.sender,
            56: self.target,
            45: ref_seq_num, # RefSeqNum
            371: ref_tag_id if ref_tag_id else '', # RefTagID (optional)
            372: 'SESSION', # RefMsgType (assuming session level reject for now) - this needs context
            373: session_reject_reason, # SessionRejectReason
            58: text # Text
        })
        # SeqNum and SendingTime will be added by send_message
        await self.send_message(reject_message)
        # Setting incoming sequence number after a reject is complex.
        # Standard says "The FIX session protocol does not provide for retransmission of Session Level Reject messages."
        # Incrementing incoming seq num might be incorrect if the reject is for a message that itself had a problematic seq num.
        # self.message_store.set_incoming_sequence_number(ref_seq_num + 1) # <<< Review this line carefully based on FIX spec for rejects
        self.logger.info(f"Sent Reject message for RefSeqNum {ref_seq_num} with reason {session_reject_reason}: {text}")


    async def handle_message(self, data_str: str): # Expecting a decoded string from network.receive
        async with self.lock: # Lock for message processing if multiple messages could arrive rapidly (though asyncio is single-threaded)
            parsed_message = None
            try:
                # The `from_wire` method should ideally handle multiple messages in a single data chunk if that can happen
                # For now, assume data_str is a single FIX message string
                parsed_message = self.fixmsg().from_wire(data_str, codec=self.codec)
            except Exception as e:
                self.logger.error(f"Failed to parse message string: {data_str[:100]}... Error: {e}")
                # Determine RefSeqNum for reject if possible, otherwise it's problematic.
                # This is a low-level parsing error. A general session reject might be needed if seq num unknown.
                # await self.send_reject_message(0, 0, 0, f"Failed to parse message: {e}") # Reject Code 0: Invalid tag number (generic)
                return
    
            self.logger.info(f"Received: {parsed_message.get(35)} (SeqNum {parsed_message.get(34)})")
            
            # TODO: Add proper checksum validation if not handled by from_wire or if done separately
            # if parsed_message.checksum() != parsed_message.get(10):
            #     self.logger.error("Checksum validation failed for received message.")
            #     await self.send_reject_message(parsed_message.get(34), 10, 5, "Invalid checksum") # Reject Code 5: Checksum failure
            #     return
            
            # Sequence number validation
            # This logic is critical and might need to be more nuanced for Logon messages (MsgType A)
            # as per FIX spec (e.g. expected seq num for Logon can be 1).
            msg_type = parsed_message.get(35)
            received_seq_num = int(parsed_message.get(34)) # Ensure it's an int

            if msg_type == 'A': # Logon
                 # For an incoming Logon, if we are an acceptor, we might expect 1 if it's a fresh session.
                 # Or, if resuming, it could be higher. This needs careful handling in LogonHandler.
                 # For now, basic check. LogonHandler should do the detailed validation.
                 pass # Let LogonHandler manage sequence for Logon.
            elif msg_type == '5': # Logout - process even if seq num is off, but log it
                pass
            elif msg_type == '4' and parsed_message.get(123, 'N') == 'N': # SequenceReset-Reset (123=N, GapFillFlag)
                # This message intends to reset the sequence. Special handling in SequenceResetHandler.
                pass
            else: # For most other messages
                expected_seq_num = self.message_store.get_next_incoming_sequence_number()
                if received_seq_num < expected_seq_num:
                    self.logger.warning(f"Received message with lower than expected sequence number. Expected: {expected_seq_num}, Received: {received_seq_num}. Possible duplicate or error.")
                    # Per FIX spec, for sequence numbers less than expected and not a SeqReset-Reset:
                    # "generate a Logout message and terminate the connection."
                    # This is a serious condition.
                    text = f"MsgSeqNum too low, expected {expected_seq_num} but received {received_seq_num}"
                    await self.send_logout_message(text=text)
                    await self.disconnect(graceful=False)
                    return
                elif received_seq_num > expected_seq_num:
                    self.logger.warning(f"Sequence number gap detected. Expected: {expected_seq_num}, Received: {received_seq_num}. Requesting resend.")
                    # Trigger ResendRequest logic (typically done by ResendRequestHandler or similar)
                    # This might involve calling a method like self.initiate_resend_request(expected_seq_num, received_seq_num-1)
                    # For now, let's assume ResendRequestHandler is invoked by MessageProcessor if needed.
                    # The current ResendRequestHandler seems to handle incoming Resend Requests, not initiate them.
                    # This engine needs a way to INITIATE a resend request.
                    # For simplicity here, we'll let it pass to the processor, which might not be right.
                    # A proper engine would send a Resend Request here.
                    # This part needs implementation of sending a Resend Request.
                    pass # Fall through to MessageProcessor, which needs to be smart or we need explicit resend logic here.


            # Store and process the message
            # Storing raw string `data_str` as it was received.
            self.message_store.store_message(self.version, self.sender, self.target, received_seq_num, data_str)
            
            # Only update sequence number if it's not a SequenceReset-Reset that handles its own seq num update.
            if not (msg_type == '4' and parsed_message.get(123, 'N') == 'N'):
                self.message_store.set_incoming_sequence_number(received_seq_num + 1)
            
            # Let the registered handler for this message type process it.
            await self.message_processor.process_message(parsed_message)

    async def disconnect(self, graceful=True):
        self.logger.info(f"Disconnecting {'gracefully' if graceful else 'abruptly'}...")
        if graceful and self.state_machine.state.name == 'ACTIVE':
            try:
                await self.send_logout_message()
            except Exception as e_logout:
                self.logger.error(f"Error sending logout message during graceful disconnect: {e_logout}")

        if self.network: # Ensure network object exists
            await self.network.disconnect() # Close TCP/IP connection
        
        if self.heartbeat and self.heartbeat.is_running():
            await self.heartbeat.stop()

        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                self.logger.info("Scheduler task cancelled.")
        
        self.retry_attempts = 0 # Reset retry attempts on disconnect
        if self.state_machine.state.name != 'DISCONNECTED':
            self.state_machine.on_event('disconnect') # Ensure final state is Disconnected
        self.logger.info("Disconnected successfully.")


    async def reset_sequence_numbers(self):
        self.message_store.reset_sequence_numbers()
        self.logger.info("Sequence numbers reset to 1 for both inbound and outbound.")

    async def set_inbound_sequence_number(self, seq_num):
        self.message_store.set_incoming_sequence_number(seq_num)
        self.logger.info(f"Inbound sequence number set to {seq_num}")

    async def set_outbound_sequence_number(self, seq_num):
        self.message_store.set_outgoing_sequence_number(seq_num)
        self.logger.info(f"Outbound sequence number set to {seq_num}")

    async def handle_logout_message_received(self, message: FixMessage): # Specific handler for when Logout is received
        self.logger.info("Logout message received from counterparty.")
        # If we are active, we should respond with our own Logout if we didn't initiate.
        if self.state_machine.state.name == 'ACTIVE': # Check if we are in an active session
            self.logger.info("Responding to Logout with our own Logout.")
            await self.send_logout_message(text="Logout acknowledged") # Send confirming Logout
        await self.disconnect(graceful=False) # Disconnect connection immediately after handling

    async def send_logout_message(self, text: str = "Operator requested logout"):
        if not self.network.running and self.state_machine.state.name == 'DISCONNECTED': # Check if already disconnected or not connected
            self.logger.info("Cannot send Logout: Not connected or network not running.")
            return

        logout_message = self.fixmsg()
        logout_message.update({
            35: '5',  # MsgType: Logout
            49: self.sender,
            56: self.target,
            58: text # Text explanation
        })
        # MsgSeqNum and SendingTime will be added by send_message
        try:
            await self.send_message(logout_message)
            self.logger.info(f"Sent Logout message: {text}")
        except Exception as e:
            self.logger.error(f"Failed to send Logout message: {e}")
        finally:
            # Transition state after sending logout, or let disconnect handle it
            if self.state_machine.state.name != 'LOGOUT_IN_PROGRESS' and self.state_machine.state.name != 'DISCONNECTED':
                 self.state_machine.on_event('logout_sent') # Or some similar event

