from functools import wraps
import asyncio
import logging # Import logging module
# from pyfixmsg_plus.fixengine.state_machine import StateMachine, Disconnected, LogonInProgress, LogoutInProgress, Active, Reconnecting # Not directly used here, but engine has it
# from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory # We'll use engine.fixmsg()

# Define the logging decorator
def logging_decorator(handler_func):
    @wraps(handler_func)
    async def wrapper(self, message): # Ensure wrapper is async if handler_func is async
        msg_type_for_log = message.get(35, "UNKNOWN_TYPE")
        seq_num_for_log = message.get(34, "NO_SEQ")
        if hasattr(self, 'logger') and self.logger:
            # Ensure codec is available and message is suitable for to_wire
            log_message_str = message.to_wire(self.engine.codec) if hasattr(self.engine, 'codec') and hasattr(message, 'to_wire') else str(message)
            self.logger.debug(f"Handling {msg_type_for_log} (Seq {seq_num_for_log}). Incoming: {log_message_str}")
        else: # Fallback if logger not set up on self
            print(f"Logging message before handling: {message}")
        
        result = await handler_func(self, message) # Await the async handler
        
        if hasattr(self, 'logger') and self.logger:
            self.logger.debug(f"Finished handling {msg_type_for_log} (Seq {seq_num_for_log}).")
        else:
            print(f"Logging message after handling: {message}")
        return result
    return wrapper

# Base class for message handlers
class MessageHandler:
    def __init__(self, message_store, state_machine, application, engine): # Added engine
        self.message_store = message_store
        self.state_machine = state_machine
        self.application = application
        self.engine = engine # Store the engine instance
        # Setup a logger for each handler instance
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")


    async def handle(self, message): # Made handle async as most handlers will be
        raise NotImplementedError

# Concrete implementations of message handlers
class LogonHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message): # message is the received Logon message
        msg_type = message.get(35)
        if msg_type != 'A':
            self.logger.error(f"LogonHandler received non-Logon message: {msg_type}")
            return

        received_sender_comp_id = message.get(49)
        received_target_comp_id = message.get(56)
        received_seq_num_str = message.get(34)
        received_heartbeat_interval_str = message.get(108)
        reset_seq_num_flag = message.get(141) == 'Y' # Check ResetSeqNumFlag

        if not received_seq_num_str or not received_seq_num_str.isdigit():
            reason = f"Invalid or missing MsgSeqNum (34) in Logon: '{received_seq_num_str}'"
            self.logger.error(reason)
            await self.engine.send_logout_message(text=reason)
            await self.engine.disconnect(graceful=False)
            return
        received_seq_num = int(received_seq_num_str)

        if not received_heartbeat_interval_str or not received_heartbeat_interval_str.isdigit():
            reason = f"Invalid or missing HeartBtInt (108) in Logon: '{received_heartbeat_interval_str}'"
            self.logger.error(reason)
            # FIX spec: "Absence of this field should be interpreted as "no heart beat monitoring"
            # However, if present and invalid, it's an issue.
            # For simplicity, we can reject if present and invalid. Or default to engine's interval.
            # Let's require it for now if the tag is present.
            await self.engine.send_logout_message(text=reason)
            await self.engine.disconnect(graceful=False)
            return
        received_heartbeat_interval = int(received_heartbeat_interval_str)


        if self.engine.mode == 'acceptor':
            self.logger.info(f"Acceptor ({self.engine.sender}) received Logon from Initiator ({received_sender_comp_id}): Seq={received_seq_num}, HBInt={received_heartbeat_interval}, ResetFlag={reset_seq_num_flag}")

            # 1. CompID Validation
            if received_sender_comp_id != self.engine.target or received_target_comp_id != self.engine.sender:
                reason = f"Invalid CompIDs in Logon. Expected Sender={self.engine.target}/Target={self.engine.sender}. Got Sender={received_sender_comp_id}/Target={received_target_comp_id}"
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return

            # 2. Sequence Number Validation
            expected_incoming_seq_num = self.message_store.get_next_incoming_sequence_number()

            if reset_seq_num_flag:
                self.logger.info(f"ResetSeqNumFlag=Y received from {received_sender_comp_id}. Acceptor will reset its sequence numbers.")
                if received_seq_num != 1:
                    reason = f"Invalid Logon: ResetSeqNumFlag(141)=Y but MsgSeqNum(34)={received_seq_num} (expected 1)."
                    self.logger.error(reason)
                    await self.engine.send_logout_message(text=reason)
                    await self.engine.disconnect(graceful=False)
                    return
                # Acceptor resets its sequence numbers to match initiator's reset
                await self.engine.reset_sequence_numbers() # Resets both in and out for the store to 1
                expected_incoming_seq_num = 1 # After reset, we expect 1
            
            if received_seq_num < expected_incoming_seq_num:
                reason = f"MsgSeqNum too low in Logon. Expected >= {expected_incoming_seq_num}, Got {received_seq_num}."
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return
            elif received_seq_num > expected_incoming_seq_num:
                # If MsgSeqNum is higher than expected on a Logon, it's an error.
                # The initiator should have sent a ResendRequest if it thought the acceptor was ahead.
                # Or, if ResetSeqNumFlag=Y was intended, it should have been 1.
                reason = f"MsgSeqNum too high in Logon. Expected {expected_incoming_seq_num}, Got {received_seq_num}."
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return
            
            # If sequence number is correct (i.e., received_seq_num == expected_incoming_seq_num)
            self.logger.info(f"Acceptor: Incoming Logon from {received_sender_comp_id} is valid (SeqNum {received_seq_num}).")
            self.message_store.increment_incoming_sequence_number() # Crucial: Update store's next expected

            self.engine.heartbeat.set_remote_interval(received_heartbeat_interval)

            # Send Logon response
            acceptor_logon_response = self.engine.fixmsg()
            acceptor_logon_response.update({
                35: 'A',
                108: self.engine.heartbeat_interval 
            })
            if reset_seq_num_flag: # If initiator reset, acceptor also includes ResetSeqNumFlag=Y
                acceptor_logon_response[141] = 'Y'
                # SeqNum will be 1 due to reset_sequence_numbers and get_next_outgoing_sequence_number
            
            # CompIDs, SeqNum, SendingTime added by engine.send_message
            await self.engine.send_message(acceptor_logon_response)
            self.logger.info(f"Acceptor sent Logon response to {received_sender_comp_id} (SeqNum {acceptor_logon_response.get(34)}).")

            self.state_machine.on_event('active_session')
            if self.engine.heartbeat: await self.engine.heartbeat.start()
            self.logger.info(f"FIX session with {received_sender_comp_id} is now ACTIVE.")

        elif self.engine.mode == 'initiator':
            self.logger.info(f"Initiator ({self.engine.sender}) received Logon response from Acceptor ({received_sender_comp_id}): Seq={received_seq_num}, HBInt={received_heartbeat_interval}, ResetFlag={reset_seq_num_flag}")

            # 1. CompID Validation
            if received_sender_comp_id != self.engine.target or received_target_comp_id != self.engine.sender:
                reason = f"Invalid CompIDs in Logon response. Expected Sender={self.engine.target}/Target={self.engine.sender}. Got Sender={received_sender_comp_id}/Target={received_target_comp_id}"
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return

            # 2. Sequence Number Validation
            expected_incoming_seq_num = self.message_store.get_next_incoming_sequence_number()
            
            # If we (initiator) sent ResetSeqNumFlag=Y, we expect their Logon response to also have ResetSeqNumFlag=Y
            # and their sequence number should be 1.
            our_logon_had_reset = self.engine.config_manager.get('FIX', 'reset_seq_num_on_logon', 'false').lower() == 'true'
            if our_logon_had_reset:
                if not reset_seq_num_flag:
                    reason = "Initiator sent ResetSeqNumFlag=Y, but Logon response did not have it."
                    self.logger.error(reason)
                    # This is a protocol violation by acceptor. Disconnect.
                    await self.engine.send_logout_message(text=reason)
                    await self.engine.disconnect(graceful=False)
                    return
                if received_seq_num != 1:
                    reason = f"Initiator sent ResetSeqNumFlag=Y, expected MsgSeqNum=1 in response, got {received_seq_num}."
                    self.logger.error(reason)
                    await self.engine.send_logout_message(text=reason)
                    await self.engine.disconnect(graceful=False)
                    return
                # If we reset and they responded with reset and seq 1, our expected_incoming_seq_num should also be 1.
                if expected_incoming_seq_num != 1: # This implies our store wasn't reset correctly with our Logon
                    self.logger.error(f"CRITICAL INTERNAL ERROR: Initiator sent Reset, response is Reset with Seq 1, but our expected incoming is {expected_incoming_seq_num}. Forcing store reset.")
                    await self.engine.reset_sequence_numbers() # Ensure our side is also reset
                    expected_incoming_seq_num = 1


            if received_seq_num < expected_incoming_seq_num:
                reason = f"MsgSeqNum too low in Logon response. Expected >= {expected_incoming_seq_num}, Got {received_seq_num}."
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return
            elif received_seq_num > expected_incoming_seq_num:
                reason = f"MsgSeqNum too high in Logon response. Expected {expected_incoming_seq_num}, Got {received_seq_num}."
                self.logger.error(reason)
                # This could trigger a resend request from our side, but for a Logon response, it's usually a fatal error.
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return

            # If sequence number is correct
            self.logger.info(f"Initiator: Logon response from {received_sender_comp_id} is valid (SeqNum {received_seq_num}).")
            self.message_store.increment_incoming_sequence_number() # Crucial: Update store's next expected

            self.engine.heartbeat.set_remote_interval(received_heartbeat_interval)
            self.state_machine.on_event('active_session')
            # Initiator's heartbeat was already started by FixEngine.logon()
            self.logger.info(f"FIX session with {received_sender_comp_id} is now ACTIVE.")
        else:
            self.logger.error(f"LogonHandler: Unknown engine mode '{self.engine.mode}'")


class TestRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        test_req_id = message.get(112)
        if not test_req_id:
            self.logger.warning("Received TestRequest without TestReqID (112). Cannot properly respond.")
            await self.engine.send_reject_message(
                ref_seq_num=message.get(34), 
                ref_tag_id=112, 
                session_reject_reason=1, # Value is incorrect (missing)
                text="TestRequest missing TestReqID(112)",
                ref_msg_type=message.get(35)
            )
            return

        self.logger.info(f"Received TestRequest (112={test_req_id}). Responding with Heartbeat.")
        heartbeat_response = self.engine.fixmsg({
            35: '0', 112: test_req_id
        })
        await self.engine.send_message(heartbeat_response)
        self.logger.info(f"Sent Heartbeat in response to TestRequest {test_req_id}.")


class ExecutionReportHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class NewOrderHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class CancelOrderHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class OrderCancelReplaceHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class OrderCancelRejectHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class NewOrderMultilegHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class MultilegOrderCancelReplaceHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        await self.application.onMessage(message)

class ResendRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        start_seq_num_str = message.get(7)
        end_seq_num_str = message.get(16)

        if not start_seq_num_str or not start_seq_num_str.isdigit() or \
           not end_seq_num_str or not end_seq_num_str.isdigit():
            reason = f"Invalid BeginSeqNo(7) or EndSeqNo(16) in ResendRequest: Begin='{start_seq_num_str}', End='{end_seq_num_str}'"
            self.logger.error(reason)
            await self.engine.send_reject_message(
                ref_seq_num=message.get(34), 
                ref_tag_id=7 if not start_seq_num_str or not start_seq_num_str.isdigit() else 16,
                session_reject_reason=5, # Value is incorrect
                text=reason,
                ref_msg_type=message.get(35)
            )
            return

        start_seq_num = int(start_seq_num_str)
        end_seq_num = int(end_seq_num_str)
        
        self.logger.info(f"Received Resend Request: BeginSeqNo={start_seq_num}, EndSeqNo={end_seq_num}.")

        if end_seq_num != 0 and end_seq_num < start_seq_num:
            reason = f"Invalid range in ResendRequest: EndSeqNo({end_seq_num}) < BeginSeqNo({start_seq_num})"
            self.logger.error(reason)
            await self.engine.send_reject_message(
                 ref_seq_num=message.get(34), ref_tag_id=16, session_reject_reason=5, text=reason, ref_msg_type=message.get(35)
            )
            return

        effective_end_seq_num = end_seq_num
        if end_seq_num == 0:
            current_outgoing = self.message_store.get_current_outgoing_sequence_number() # Gets last *sent*
            effective_end_seq_num = current_outgoing
            self.logger.info(f"EndSeqNo=0, adjusted to current last sent: {effective_end_seq_num}.")
            if effective_end_seq_num < start_seq_num and start_seq_num > 0 : # check start_seq_num > 0 to avoid issues if current_outgoing is 0 (no messages sent yet)
                 self.logger.info(f"Adjusted EndSeqNo ({effective_end_seq_num}) is less than BeginSeqNo ({start_seq_num}). Nothing to resend.")
                 # Send a heartbeat or sequence reset to indicate end of resend process if nothing to resend
                 # For now, just log and complete. Consider sending Heartbeat.
                 # await self.engine.send_message(self.engine.fixmsg({35: '0'})) # Example: send heartbeat
                 self.logger.info(f"Completed processing Resend Request from {start_seq_num} to {end_seq_num} (effective {effective_end_seq_num}). Nothing to resend.")
                 return


        for seq_num_to_resend in range(start_seq_num, effective_end_seq_num + 1):
            # Retrieve the stored outgoing message.
            # Note: Stored messages are keyed by (version, our_sender_id, our_target_id, seq_num_of_that_message)
            stored_message_str = self.message_store.get_message(
                self.engine.version,
                self.engine.sender, 
                self.engine.target, 
                seq_num_to_resend
            )

            if stored_message_str:
                self.logger.info(f"Resending stored message for SeqNum {seq_num_to_resend}.")
                try:
                    resent_msg = self.engine.fixmsg().from_wire(stored_message_str, codec=self.engine.codec)
                    resent_msg[43] = 'Y' # PossDupFlag
                    original_sending_time = resent_msg.get(52) 
                    if original_sending_time:
                        resent_msg[122] = original_sending_time # OrigSendingTime
                    
                    # SendingTime(52) will be updated by self.engine.send_message()
                    # MsgSeqNum(34) is already correct from the stored message.
                    await self.engine.send_message(resent_msg)
                except Exception as e:
                    self.logger.error(f"Error parsing or preparing stored message {seq_num_to_resend} for resend: {e}. Sending GapFill.", exc_info=True)
                    await self.send_gap_fill(seq_num_to_resend, seq_num_to_resend) # Gap fill for this single message
            else:
                self.logger.warning(f"Message for SeqNum {seq_num_to_resend} not found in store. Sending GapFill.")
                await self.send_gap_fill(seq_num_to_resend, seq_num_to_resend) # Gap fill for this single message
        
        self.logger.info(f"Completed processing Resend Request from {start_seq_num} to {end_seq_num} (effective {effective_end_seq_num}).")
        # Consider sending a Heartbeat or SequenceReset (mode Reset) after completing a resend request,
        # especially if EndSeqNo was 0, to signal the end of the resend stream.
        # This depends on counterparty expectations. For now, just log completion.

    async def send_gap_fill(self, begin_gap_seq_num, end_gap_seq_num):
        """Helper to send a SequenceReset-GapFill message."""
        # For a single message gap fill, begin_gap_seq_num == end_gap_seq_num
        # NewSeqNo in GapFill is the seq num of the *next* message after the gap.
        next_seq_no_after_gap = end_gap_seq_num + 1
        
        self.logger.info(f"Sending SequenceReset-GapFill for range {begin_gap_seq_num}-{end_gap_seq_num}. NewSeqNo will be {next_seq_no_after_gap}.")
        gap_fill_msg = self.engine.fixmsg()
        gap_fill_msg.update({
            35: '4', # MsgType: Sequence Reset
            36: next_seq_no_after_gap, # NewSeqNo: The sequence number of the next message to be expected by the receiver
            123: 'Y' # GapFillFlag
        })
        # MsgSeqNum for this SequenceReset message itself will be set by send_message
        await self.engine.send_message(gap_fill_msg)


class SequenceResetHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        gap_fill_flag = message.get(123) == 'Y' # More direct boolean check
        new_seq_no_str = message.get(36)
        msg_seq_num_header_str = message.get(34)

        if not new_seq_no_str or not new_seq_no_str.isdigit():
            reason = f"Invalid or missing NewSeqNo(36) in SequenceReset: '{new_seq_no_str}'"
            self.logger.error(reason)
            await self.engine.send_reject_message(message.get(34) or 0, 36, 5, reason, message.get(35))
            return
        new_seq_no = int(new_seq_no_str)
        
        # msg_seq_num_header is already validated by FixEngine.handle_message before this point
        msg_seq_num_header = int(msg_seq_num_header_str) 

        self.logger.info(f"Received SequenceReset: NewSeqNo={new_seq_no}, GapFillFlag={gap_fill_flag}, HeaderSeqNum={msg_seq_num_header}")

        current_expected_incoming = self.message_store.get_next_incoming_sequence_number()

        # Validation: NewSeqNo MUST be > MsgSeqNum of the Sequence Reset message itself, if not GapFill.
        # And NewSeqNo must not decrease the sequence number, unless it's a GapFill for an already processed sequence (which is unusual).
        if new_seq_no <= msg_seq_num_header and not gap_fill_flag:
             self.logger.warning(f"SequenceReset-Reset: NewSeqNo ({new_seq_no}) must be greater than its own header MsgSeqNum ({msg_seq_num_header}).")
             # This is often a protocol violation.
             await self.engine.send_reject_message(msg_seq_num_header, 36, 5, "NewSeqNo must be > MsgSeqNum for SequenceReset-Reset", message.get(35))
             return

        if not gap_fill_flag: # Mode is Reset (GapFillFlag='N' or not present)
            if new_seq_no <= current_expected_incoming:
                reason = f"SequenceReset-Reset: NewSeqNo ({new_seq_no}) must be greater than current expected incoming ({current_expected_incoming})."
                self.logger.error(reason)
                await self.engine.send_reject_message(msg_seq_num_header, 36, 5, reason, message.get(35))
                return
            
            self.logger.info(f"Processing SequenceReset-Reset. Setting next incoming and outgoing to {new_seq_no}.")
            self.message_store.set_incoming_sequence_number(new_seq_no)
            self.message_store.set_outgoing_sequence_number(new_seq_no) # Reset our outgoing as well
            self.logger.info(f"Both incoming and outgoing sequence numbers reset to {new_seq_no}.")
            # A Heartbeat should be sent after a Reset to confirm the new sequence.
            await self.engine.send_message(self.engine.fixmsg({35: '0'})) # Send Heartbeat

        else: # Mode is Gap Fill (GapFillFlag='Y')
            # For GapFill, NewSeqNo sets the next expected incoming sequence number.
            # It implies all messages from current_expected_incoming up to NewSeqNo-1 are to be ignored.
            if new_seq_no <= current_expected_incoming:
                # This implies the GapFill is for a sequence we've already processed or are about to.
                # This is unusual but not strictly a protocol violation if NewSeqNo refers to a future message.
                # However, if NewSeqNo is less than the message's own sequence number, it's an error.
                self.logger.warning(f"SequenceReset-GapFill: NewSeqNo ({new_seq_no}) is not greater than current expected incoming ({current_expected_incoming}). This might be an issue or an attempt to fill already processed messages.")
                if new_seq_no <= msg_seq_num_header:
                     await self.engine.send_reject_message(msg_seq_num_header, 36, 5, "NewSeqNo in GapFill must be > MsgSeqNum of SequenceReset itself", message.get(35))
                     return
            
            self.logger.info(f"Processing SequenceReset-GapFill. Setting next expected incoming to {new_seq_no}.")
            self.message_store.set_incoming_sequence_number(new_seq_no)
            # Outgoing sequence is NOT affected by a GapFill.


class RejectHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        ref_seq_num = message.get(45) 
        ref_tag_id = message.get(371)
        ref_msg_type = message.get(372)
        reject_reason_code = message.get(373) 
        text = message.get(58) 
        self.logger.warning(f"Received Session-Level Reject: RefSeqNum={ref_seq_num}, RefTagID={ref_tag_id}, RefMsgType={ref_msg_type}, ReasonCode={reject_reason_code}, Text='{text}'")
        
        if hasattr(self.application, 'onReject'):
            await self.application.onReject(message)
        
        # FIX spec suggests that after sending/receiving certain types of Rejects, a Logout is appropriate.
        # e.g., "Invalid MsgType", "Required tag missing", "Tag not defined for this message type", "Value is incorrect"
        # For simplicity, we don't auto-logout here, but a production system might.


class LogoutHandler(MessageHandler): 
    @logging_decorator
    async def handle(self, message): # Handles received Logout (35=5)
        text = message.get(58, "")
        received_seq_num = message.get(34) # Already validated by FixEngine
        self.logger.info(f"Logout (Seq={received_seq_num}) received from counterparty. Text: '{text}'.")
        
        # FIX: "Upon receipt of a Logout message, the session is considered terminated."
        # "The recipient of the Logout message should send a confirming Logout message ..."
        # "... unless the session is already in a logged out state or if the Logout ... itself has a sequence number problem."
        
        # Check our current state. If we are already disconnected or logging out, no need to confirm.
        current_engine_state = self.state_machine.state.name
        if current_engine_state not in ['DISCONNECTED', 'LOGOUT_IN_PROGRESS']:
            self.logger.info(f"Session was {current_engine_state}. Sending confirming Logout.")
            await self.engine.send_logout_message(text="Logout Acknowledged by Handler")
        else:
            self.logger.info(f"Session already in state {current_engine_state}. Not sending confirming Logout from handler.")

        # The engine's disconnect will handle final state transition and TCP close.
        # We initiate it here because the session is now over from FIX perspective.
        await self.engine.disconnect(graceful=False) 
        self.logger.info("LogoutHandler initiated engine disconnect.")


class HeartbeatHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        # Received a Heartbeat (35=0)
        test_req_id_in_hb = message.get(112) # Check if this heartbeat is in response to a TestRequest
        self.logger.debug(f"Received Heartbeat. TestReqID (112) in Heartbeat: {test_req_id_in_hb}")
        
        if self.engine.heartbeat:
            # Call the centralized processing method in the Heartbeat class
            self.engine.heartbeat.process_incoming_heartbeat(test_req_id_in_hb)
        else:
            self.logger.warning("Received Heartbeat, but FixEngine.heartbeat object is not available.")

class MessageProcessor:
    def __init__(self, message_store, state_machine, application, engine): 
        self.handlers = {}
        self.message_store = message_store
        self.state_machine = state_machine
        self.application = application
        self.engine = engine 
        self.logger = logging.getLogger(self.__class__.__name__)


    def register_handler(self, message_type, handler_instance): 
        self.handlers[message_type] = handler_instance
        self.logger.debug(f"Registered handler for message type '{message_type}': {handler_instance.__class__.__name__}")


    async def process_message(self, message):
        message_type = message.get(35)
        handler = self.handlers.get(message_type)
        if handler:
            # self.logger.debug(f"Processing message type '{message_type}' with {handler.__class__.__name__}") # Covered by decorator
            await handler.handle(message) 
        else:
            ref_seq_num_str = message.get(34)
            self.logger.warning(f"No handler registered for message type: {message_type}. Message SeqNum: {ref_seq_num_str}. Content: {message.to_wire(self.engine.codec) if hasattr(self.engine, 'codec') else message}")
            # Standard behavior for unhandled *application* message types during an active session might be to ignore or pass to a generic app handler.
            # For unhandled *session* message types, a Reject is often appropriate.
            if self.state_machine.state.name == 'ACTIVE':
                # Check if it's an admin message (upper case or single digit) vs application (lower case)
                # This is a simplification; FIX spec defines admin messages.
                is_admin_type = (len(message_type) == 1 and (message_type.isupper() or message_type.isdigit())) or \
                                (len(message_type) == 2 and message_type.isupper() and message_type[0] == 'A') # e.g. AB, AC

                if is_admin_type: # If it looks like an admin message we don't handle
                    self.logger.error(f"Unhandled Admin Message Type: {message_type}. Sending Reject.")
                    await self.engine.send_reject_message(
                        ref_seq_num=ref_seq_num_str if ref_seq_num_str and ref_seq_num_str.isdigit() else 0,
                        ref_tag_id=35, # Tag 35 (MsgType) caused the issue
                        session_reject_reason=3, # Invalid MsgType
                        text=f"Unsupported admin message type: {message_type}",
                        ref_msg_type=message_type
                    )
                else: # Likely an application message the app doesn't explicitly handle via a registered handler
                    self.logger.info(f"Passing unhandled application message type {message_type} to generic application.onMessage.")
                    if hasattr(self.application, 'onMessage'): # Allow generic passthrough
                        await self.application.onMessage(message)
                    else:
                        self.logger.warning(f"Application does not have a generic onMessage method for type {message_type}.")
