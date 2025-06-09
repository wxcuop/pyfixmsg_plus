from functools import wraps
import asyncio
import logging # Import logging module
# from pyfixmsg_plus.fixengine.state_machine import StateMachine, Disconnected, LogonInProgress, LogoutInProgress, Active, Reconnecting # Not directly used here, but engine has it
# from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory # We'll use engine.fixmsg()

# Define the logging decorator
def logging_decorator(handler_func):
    @wraps(handler_func)
    async def wrapper(self, message): # Ensure wrapper is async if handler_func is async
        if hasattr(self, 'logger') and self.logger:
            self.logger.debug(f"Handling {message.get(35)} (Seq {message.get(34)}). Incoming: {message.to_wire(self.engine.codec) if hasattr(self.engine, 'codec') else message}")
        else: # Fallback if logger not set up on self
            print(f"Logging message before handling: {message}")
        
        result = await handler_func(self, message) # Await the async handler
        
        if hasattr(self, 'logger') and self.logger:
            self.logger.debug(f"Finished handling {message.get(35)} (Seq {message.get(34)}).")
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
        received_seq_num = int(message.get(34))
        received_heartbeat_interval = int(message.get(108))

        if self.engine.mode == 'acceptor':
            self.logger.info(f"Acceptor received Logon from Initiator ({received_sender_comp_id}): Seq={received_seq_num}, HBInt={received_heartbeat_interval}")

            # Validate incoming Logon
            # 1. CompIDs
            if received_sender_comp_id != self.engine.target or received_target_comp_id != self.engine.sender:
                reason = f"Invalid CompIDs. Expected Sender={self.engine.target}, Target={self.engine.sender}. Got Sender={received_sender_comp_id}, Target={received_target_comp_id}"
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return

            # 2. Sequence Number (Basic check for now, more sophisticated logic might be needed for session resumption)
            # For a new session, acceptor expects 1.
            expected_incoming_seq_num = self.message_store.get_next_incoming_sequence_number()
            if self.message_store.is_new_session() and received_seq_num != 1:
                 # If it's a brand new session from store's perspective, but initiator sends > 1, it's an issue.
                 # However, if the store already has a higher sequence number (e.g. from a previous connection attempt that stored it),
                 # then expected_incoming_seq_num would be > 1.
                 # FIX spec: "The first message from the initiator of the session must be a Logon message with MsgSeqNum(34) = 1."
                 # This implies if the acceptor's expected_incoming_seq_num is also 1, they match.
                 # If acceptor expected > 1 (resumption) but got 1, initiator is resetting. Acceptor might need to reset too.
                 # This area is complex. For now, a simple check for a "fresh" acceptor expecting 1.
                if expected_incoming_seq_num == 1 and received_seq_num != 1 :
                    reason = f"Invalid MsgSeqNum for new session. Expected 1, Got {received_seq_num}"
                    self.logger.error(reason)
                    # According to FIX spec, if MsgSeqNum is too high on initial Logon, respond with Logout.
                    await self.engine.send_logout_message(text=reason)
                    await self.engine.disconnect(graceful=False)
                    return
            elif received_seq_num < expected_incoming_seq_num :
                reason = f"MsgSeqNum too low. Expected >= {expected_incoming_seq_num}, Got {received_seq_num}"
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return
            # If received_seq_num > expected_incoming_seq_num, standard is to send Resend Request after Logon.
            # But for Logon itself, it must be the expected. If it's higher, it's an error for the Logon message itself.

            # If all validations pass for acceptor:
            self.logger.info(f"Acceptor: Incoming Logon from {received_sender_comp_id} is valid.")
            self.engine.heartbeat.set_remote_interval(received_heartbeat_interval) # Store initiator's heartbeat interval

            # Send Logon response
            acceptor_logon_response = self.engine.fixmsg()
            acceptor_logon_response.update({
                35: 'A',
                49: self.engine.sender, # Acceptor's SenderCompID
                56: received_sender_comp_id, # Acceptor's TargetCompID is the Initiator's SenderCompID
                34: self.message_store.get_next_outgoing_sequence_number(),
                108: self.engine.heartbeat_interval # Acceptor's HeartBtInt
            })
            await self.engine.send_message(acceptor_logon_response)
            self.logger.info(f"Acceptor sent Logon response to {received_sender_comp_id}.")

            self.state_machine.on_event('active_session') # Or equivalent event to transition to Active
            await self.engine.heartbeat.start()
            self.logger.info(f"FIX session is now ACTIVE with {received_sender_comp_id}.")

        elif self.engine.mode == 'initiator':
            # Initiator received a Logon response from Acceptor
            self.logger.info(f"Initiator received Logon response from Acceptor ({received_sender_comp_id}): Seq={received_seq_num}, HBInt={received_heartbeat_interval}")

            # Validate incoming Logon response
            if received_sender_comp_id != self.engine.target or received_target_comp_id != self.engine.sender:
                reason = f"Invalid CompIDs in Logon response. Expected Sender={self.engine.target}, Target={self.engine.sender}. Got Sender={received_sender_comp_id}, Target={received_target_comp_id}"
                self.logger.error(reason)
                await self.engine.send_logout_message(text=reason) # Initiator might send logout
                await self.engine.disconnect(graceful=False)
                return

            # Sequence number check (basic for now)
            expected_incoming_seq_num = self.message_store.get_next_incoming_sequence_number()
            if received_seq_num != expected_incoming_seq_num:
                reason = f"Invalid MsgSeqNum in Logon response. Expected {expected_incoming_seq_num}, Got {received_seq_num}"
                self.logger.error(reason)
                # This could trigger a resend request or a logout depending on the exact FIX rules for Logon response seq numbers
                await self.engine.send_logout_message(text=reason)
                await self.engine.disconnect(graceful=False)
                return

            # If all validations pass for initiator:
            self.logger.info(f"Initiator: Logon response from {received_sender_comp_id} is valid.")
            self.engine.heartbeat.set_remote_interval(received_heartbeat_interval)

            self.state_machine.on_event('active_session') # Transition to Active
            # Initiator's heartbeat was already started after it sent its Logon.
            self.logger.info(f"FIX session is now ACTIVE with {received_sender_comp_id}.")
        else:
            self.logger.error(f"LogonHandler: Unknown engine mode '{self.engine.mode}'")


class TestRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        # A TestRequest (MsgType=1) requires a Heartbeat (MsgType=0) in response,
        # containing the TestReqID (Tag 112) from the TestRequest.
        test_req_id = message.get(112)
        if not test_req_id:
            self.logger.warning("Received TestRequest without TestReqID (112). Cannot properly respond.")
            # Optionally send a session-level reject here
            return

        self.logger.info(f"Received TestRequest (112={test_req_id}). Responding with Heartbeat.")
        heartbeat_response = self.engine.fixmsg()
        heartbeat_response.update({
            35: '0', # MsgType: Heartbeat
            112: test_req_id # Echoing TestReqID
        })
        # Other standard header fields (Sender, Target, SeqNum, SendingTime) will be added by engine.send_message()
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
        # This handler processes an incoming Resend Request (35=2)
        start_seq_num = int(message.get(7))    # BeginSeqNo
        end_seq_num = int(message.get(16))     # EndSeqNo
        self.logger.info(f"Received Resend Request: BeginSeqNo={start_seq_num}, EndSeqNo={end_seq_num}.")

        # If EndSeqNo is 0, it means resend all messages from BeginSeqNo up to the current highest sent.
        if end_seq_num == 0:
            # This should be the next sequence number to be sent by *this* side (the one processing the resend request)
            # minus 1, as it represents the last message of the range.
            end_seq_num = self.message_store.get_current_outgoing_sequence_number() -1 # Corrected: use current, not next
            self.logger.info(f"EndSeqNo=0, adjusted to {end_seq_num} (current outgoing seq - 1).")


        for seq_num_to_resend in range(start_seq_num, end_seq_num + 1):
            # Retrieve the stored outgoing message
            # The message_store.get_message should ideally retrieve based on its own outgoing seq num.
            # The parameters version, sender, target for get_message might need to be self.engine.version etc.
            # if the store keying requires it for outgoing messages.
            # Let's assume get_outgoing_message(seq_num) exists or adapt.
            # For now, using existing get_message, assuming it can fetch outgoing.
            stored_message_str = self.message_store.get_message(
                self.engine.version,
                self.engine.sender, # Our sender ID for the message we originally sent
                self.engine.target, # Our target ID for the message we originally sent
                seq_num_to_resend
            )

            if stored_message_str:
                self.logger.info(f"Resending stored message for SeqNum {seq_num_to_resend}.")
                # The stored message is a raw string. We need to parse it, set PossDupFlag, and resend.
                resent_msg = self.engine.fixmsg().from_wire(stored_message_str, codec=self.engine.codec)
                
                # Set PossDupFlag(43)=Y
                resent_msg[43] = 'Y'
                
                # OrigSendingTime(122) should be set to the SendingTime(52) of the original message.
                # This requires storing SendingTime or parsing it from the stored_message_str.
                original_sending_time = resent_msg.get(52) # Assume it's still there
                if original_sending_time:
                    resent_msg[122] = original_sending_time
                
                # SendingTime(52) will be updated by self.engine.send_message() to current time.
                # MsgSeqNum(34) should remain the original sequence number.
                
                await self.engine.send_message(resent_msg) # send_message will handle new SendingTime, but keep original SeqNum
            else:
                self.logger.warning(f"Cannot resend message for SeqNum {seq_num_to_resend}: Not found in store. Sending GapFill.")
                # Send Sequence Reset - Gap Fill (35=4, 123=Y)
                gap_fill_msg = self.engine.fixmsg()
                gap_fill_msg.update({
                    35: '4', # MsgType: Sequence Reset
                    36: seq_num_to_resend, # NewSeqNo (the number of the message being gap-filled)
                    123: 'Y' # GapFillFlag
                })
                # Sender, Target, outgoing MsgSeqNum, SendingTime added by send_message
                await self.engine.send_message(gap_fill_msg)
        
        # After resending messages or sending Gap Fills, a Heartbeat or other message might be expected
        # to confirm the end of the resend process if the original EndSeqNo was high.
        # Or, a Sequence Reset - Reset might be needed if EndSeqNo was 0 and we are resetting to a new higher sequence.
        # This depends on the specific scenario and counterparty expectations.
        # For now, just completing the loop. Consider if a final Heartbeat is needed.
        self.logger.info(f"Completed processing Resend Request from {start_seq_num} to {end_seq_num}.")


class SequenceResetHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        gap_fill_flag = message.get(123, 'N')  # GapFillFlag (Tag 123), default to 'N' if not present
        new_seq_no = int(message.get(36))    # NewSeqNo (Tag 36)
        msg_seq_num_header = int(message.get(34)) # MsgSeqNum from the header of the SequenceReset message

        self.logger.info(f"Received SequenceReset: NewSeqNo={new_seq_no}, GapFillFlag={gap_fill_flag}, Header SeqNum={msg_seq_num_header}")

        # Standard validation: NewSeqNo MUST be greater than expected MsgSeqNum of the Sequence Reset message itself.
        # This means new_seq_no must be > msg_seq_num_header.
        # Also, NewSeqNo must not decrement the session's expected incoming sequence number.
        current_expected_incoming = self.message_store.get_next_incoming_sequence_number()

        if new_seq_no < msg_seq_num_header : # This check is often debated, but some systems enforce NewSeqNo > HeaderSeqNum
             self.logger.warning(f"SequenceReset: NewSeqNo ({new_seq_no}) is not greater than its own header MsgSeqNum ({msg_seq_num_header}). This might be an issue.")
             # Depending on strictness, could reject.

        if new_seq_no <= current_expected_incoming and gap_fill_flag == 'N': # For Reset mode only
            # "Value of NewSeqNo (36) must be greater than current expected sequence number" for Reset mode.
            # For GapFill mode (Y), NewSeqNo can be <= current_expected_incoming if filling missed messages.
            reason = f"SequenceReset-Reset: NewSeqNo ({new_seq_no}) must be greater than current expected incoming sequence number ({current_expected_incoming})."
            self.logger.error(reason)
            await self.engine.send_reject_message(msg_seq_num_header, 36, 5, reason) # RejectReason 5: Value is incorrect
            return

        if gap_fill_flag == 'Y': # Gap Fill
            self.logger.info(f"Processing Sequence Reset - GapFill. Setting next expected incoming to {new_seq_no}.")
            # For GapFill, NewSeqNo is the seq num of the last message being skipped.
            # The next expected message will be NewSeqNo (not NewSeqNo + 1).
            # The standard is a bit ambiguous here. Some interpret NewSeqNo in GapFill as the *next* expected.
            # Common interpretation: NewSeqNo is the sequence number of the *next* message to be processed.
            # So if NewSeqNo is 10, messages 1-9 were "gap filled", and 10 is next.
            self.message_store.set_incoming_sequence_number(new_seq_no)
        else: # Sequence Reset - Reset (GapFillFlag='N' or not present)
            self.logger.info(f"Processing Sequence Reset - Reset. Setting next expected incoming to {new_seq_no} and next outgoing to {new_seq_no}.")
            # For Reset mode, both incoming and outgoing sequence numbers are reset.
            self.message_store.set_incoming_sequence_number(new_seq_no)
            self.message_store.set_outgoing_sequence_number(new_seq_no) # Also reset outgoing
            self.logger.info(f"Both incoming and outgoing sequence numbers reset to {new_seq_no}.")
            # A Heartbeat might be expected after a Reset to confirm.
            # await self.engine.send_message(self.engine.fixmsg({35: '0'}))


class RejectHandler(MessageHandler): # Session-Level Reject (35=3)
    @logging_decorator
    async def handle(self, message):
        ref_seq_num = message.get(45) # RefSeqNum
        reject_reason_code = message.get(373) # SessionRejectReason
        text = message.get(58) # Text
        self.logger.warning(f"Received Session-Level Reject: RefSeqNum={ref_seq_num}, ReasonCode={reject_reason_code}, Text='{text}'")
        # Application may need to be notified.
        if hasattr(self.application, 'onReject'):
            await self.application.onReject(message)
        # Depending on the reject reason, the session might need to be terminated.
        # E.g., "Invalid MsgType", "Required tag missing", "Value is incorrect for this tag" often lead to logout.


class LogoutHandler(MessageHandler): # Handles received Logout (35=5)
    @logging_decorator
    async def handle(self, message):
        text = message.get(58, "")
        self.logger.info(f"Logout message received from counterparty. Text: '{text}'.")
        # As per FIX, upon receiving a Logout, the session is over.
        # We should not send any more messages other than a confirming Logout if one was not already sent by us.
        # The FixEngine's disconnect logic usually handles sending a confirm if needed.
        if self.state_machine.state.name == 'ACTIVE':
            # If we were active and received a logout, it implies they initiated it.
            # We should send a confirming logout.
             self.logger.info("Session was active. Sending confirming Logout.")
             await self.engine.send_logout_message(text="Logout Acknowledged")

        # Regardless of sending a confirm, the session is now terminated from our end.
        self.logger.info("Transitioning to DISCONNECTED and closing network connection.")
        await self.engine.disconnect(graceful=False) # False, as they logged us out.

class HeartbeatHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        # Received a Heartbeat (35=0)
        test_req_id = message.get(112) # Check if this heartbeat is in response to a TestRequest
        self.logger.debug(f"Received Heartbeat. TestReqID (112) in Heartbeat: {test_req_id}")
        
        if self.engine.heartbeat:
            self.engine.heartbeat.last_received_time = asyncio.get_event_loop().time()
            self.engine.heartbeat.missed_heartbeats = 0 # Reset missed counter
            self.logger.debug(f"Updated last_received_time for heartbeat. Missed heartbeats reset.")

            if test_req_id and self.engine.heartbeat.test_request_id == test_req_id:
                self.logger.info(f"This Heartbeat (112={test_req_id}) satisfies our pending TestRequest.")
                self.engine.heartbeat.test_request_id = None # Clear pending TestRequest ID
            elif test_req_id:
                self.logger.warning(f"Received Heartbeat with unsolicited TestReqID (112={test_req_id}). Our pending TestReqID is {self.engine.heartbeat.test_request_id}.")
        else:
            self.logger.warning("Received Heartbeat, but FixEngine.heartbeat object is not available.")


# MessageProcessor to register and process different message handlers
class MessageProcessor:
    def __init__(self, message_store, state_machine, application, engine): # Added engine
        self.handlers = {}
        self.message_store = message_store
        self.state_machine = state_machine
        self.application = application
        self.engine = engine # Store engine instance
        self.logger = logging.getLogger(self.__class__.__name__) # Logger for MessageProcessor


    def register_handler(self, message_type, handler_instance): # Expects an already instantiated handler
        self.handlers[message_type] = handler_instance
        self.logger.debug(f"Registered handler for message type '{message_type}': {handler_instance.__class__.__name__}")


    async def process_message(self, message):
        message_type = message.get(35)
        handler = self.handlers.get(message_type)
        if handler:
            self.logger.debug(f"Processing message type '{message_type}' with {handler.__class__.__name__}")
            await handler.handle(message) # Assumes handler.handle is async
        else:
            self.logger.warning(f"No handler registered for message type: {message_type}. Message: {message.to_wire(self.engine.codec) if hasattr(self.engine, 'codec') else message}")
            # Standard behavior for unhandled message types that are not session-level admin (like application messages)
            # might be to generate a session-level Reject if the message is not an application message
            # and the session is active. For unknown session messages, it's often a Reject.
            # For now, just logging. Consider adding reject logic if session is active.
            # Example:
            # if self.state_machine.state.name == 'ACTIVE':
            #    await self.engine.send_reject_message(message.get(34), 35, 3, f"Unsupported message type: {message_type}") # RejectReason 3: Invalid MsgType
