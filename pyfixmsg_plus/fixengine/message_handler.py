from functools import wraps
import asyncio
from state_machine import StateMachine, Disconnected, Connecting, Active, Reconnecting, LogoutInProgress

# Define the logging decorator
def logging_decorator(handler_func):
    @wraps(handler_func)
    def wrapper(self, message):
        print(f"Logging message before handling: {message}")
        result = handler_func(self, message)
        print(f"Logging message after handling: {message}")
        return result
    return wrapper

# Base class for message handlers
class MessageHandler:
    def __init__(self, message_store, state_machine):
        self.message_store = message_store
        self.state_machine = state_machine

    def handle(self, message):
        raise NotImplementedError

# Concrete implementations of message handlers with logging decorator
class LogonHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        if self.state_machine.state.name not in ['Connecting', 'Active']:
            self.logger.error("Cannot logon: not connected.")
            return
        try:
            logon_message = FixMessageFactory.create_message('A')
            logon_message[49] = self.sender
            logon_message[56] = self.target
            logon_message[34] = self.message_store.get_next_outgoing_sequence_number()
            await self.send_message(logon_message)
            await self.heartbeat.start()
        except Exception as e:
            self.logger.error(f"Failed to logon: {e}")

class TestRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        print(f"Handling test request: {message}")
        await self.handle_test_request(message)

class ExecutionReportHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling execution report: {message}")

class NewOrderHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling new order: {message}")

class CancelOrderHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling cancel order: {message}")

class OrderCancelReplaceHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling order cancel/replace: {message}")

class OrderCancelRejectHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling order cancel reject: {message}")

class NewOrderMultilegHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling new order - multileg: {message}")

class MultilegOrderCancelReplaceHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling multileg order cancel/replace: {message}")

class ResendRequestHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        start_seq_num = int(message.get('7'))  # Get the start sequence number from the resend request
        end_seq_num = int(message.get('16'))  # Get the end sequence number from the resend request
        self.logger.info(f"Received Resend Request: BeginSeqNo={start_seq_num}, EndSeqNo={end_seq_num}")
        
        if end_seq_num == 0:
            end_seq_num = self.message_store.get_next_outgoing_sequence_number() - 1
        
        for seq_num in range(start_seq_num, end_seq_num + 1):
            stored_message = self.message_store.get_message(self.version, self.sender, self.target, seq_num)
            if stored_message:
                await self.send_message(stored_message)
            else:
                await self.send_gap_fill_message(seq_num)

class SequenceResetHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        gap_fill_flag = message.get('123', 'N')
        new_seq_no = int(message.get('36'))

        if new_seq_no <= self.message_store.get_next_incoming_sequence_number():
            self.logger.error("Received Sequence Reset attempting to decrease sequence number.")
            await self.send_reject_message(message.get('34'), 36, 99, "Sequence Reset attempted to decrease sequence number")
            return

        if gap_fill_flag == 'Y':
            self.logger.info(f"Processing Sequence Reset - GapFill to {new_seq_no}")
            self.message_store.set_incoming_sequence_number(new_seq_no)
        else:
            self.logger.info(f"Processing Sequence Reset - Reset to {new_seq_no}")
            self.message_store.set_incoming_sequence_number(new_seq_no)

class RejectHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.logger.warning(f"Message rejected: {message}")

class LogoutHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.logger.info(f"Logout message received: {message}")
        self.state_machine.on_event('disconnect')
        await self.disconnect()

class HeartbeatHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.heartbeat.last_received_time = asyncio.get_event_loop().time()
        if '112' in message:
            self.heartbeat.test_request_id = None

# MessageProcessor to register and process different message handlers
class MessageProcessor:
    def __init__(self, message_store, state_machine):
        self.handlers = {}
        self.message_store = message_store
        self.state_machine = state_machine

    def register_handler(self, message_type, handler):
        self.handlers[message_type] = handler

    async def process_message(self, message):
        message_type = message.get(35)  # Assuming tag 35 is the message type
        handler = self.handlers.get(message_type)
        if handler:
            await handler.handle(message)
        else:
            print(f"No handler for message type: {message_type}")

# Example usage for registering handlers
if __name__ == "__main__":
    db_path = 'fix_messages.db'
    message_store = DatabaseMessageStore(db_path)
    state_machine = StateMachine(Disconnected())
    processor = MessageProcessor(message_store, state_machine)
    
    processor.register_handler('A', LogonHandler(message_store, state_machine))
    processor.register_handler('1', TestRequestHandler(message_store, state_machine))
    processor.register_handler('8', ExecutionReportHandler(message_store, state_machine))
    processor.register_handler('D', NewOrderHandler(message_store, state_machine))
    processor.register_handler('F', CancelOrderHandler(message_store, state_machine))
    processor.register_handler('G', OrderCancelReplaceHandler(message_store, state_machine))
    processor.register_handler('9', OrderCancelRejectHandler(message_store, state_machine))
    processor.register_handler('AB', NewOrderMultilegHandler(message_store, state_machine))
    processor.register_handler('AC', MultilegOrderCancelReplaceHandler(message_store, state_machine))
    processor.register_handler('2', ResendRequestHandler(message_store, state_machine))
    processor.register_handler('4', SequenceResetHandler(message_store, state_machine))
    processor.register_handler('3', RejectHandler(message_store, state_machine))
    processor.register_handler('5', LogoutHandler(message_store, state_machine))
    processor.register_handler('0', HeartbeatHandler(message_store, state_machine))

    # Example message processing
    logon_message = FixMessageFactory.create_message('A')  # Create logon message using factory
    execution_report_message = FixMessageFactory.create_message('8')  # Create execution report message using factory

    # Note: In real usage, these would be handled within an async context
    import asyncio
    asyncio.run(processor.process_message(logon_message))
    asyncio.run(processor.process_message(execution_report_message))
