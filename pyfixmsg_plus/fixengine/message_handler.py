from functools import wraps

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
    def __init__(self, message_store):
        self.message_store = message_store

    def handle(self, message):
        raise NotImplementedError

# Concrete implementations of message handlers with logging decorator
class LogonHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        print(f"Handling logon message: {message}")
        await self.handle_logon()
        await self.heartbeat.start()  # Start the heartbeat after logon

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
        start_seq_num = int(message.get(7))  # Get the start sequence number from the resend request
        end_seq_num = int(message.get(16))  # Get the end sequence number from the resend request
        for seq_num in range(start_seq_num, end_seq_num + 1):
            msg = self.message_store.get_message(seq_num)
            if msg:
                await self.send_message(msg)
            else:
                await self.send_gap_fill(seq_num)

class SequenceResetHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        new_seq_num = int(message.get(36))  # Get the new sequence number from the sequence reset
        self.sequence_manager.reset_sequence(new_seq_num)
        self.logger.info(f"Sequence reset to {new_seq_num}")

class RejectHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.logger.warning(f"Message rejected: {message}")

class LogoutHandler(MessageHandler):
    @logging_decorator
    async def handle(self, message):
        self.logger.info(f"Logout message received: {message}")
        await self.disconnect()

# MessageProcessor to register and process different message handlers
class MessageProcessor:
    def __init__(self, message_store):
        self.handlers = {}
        self.message_store = message_store

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
    processor = MessageProcessor(message_store)
    
    processor.register_handler('A', LogonHandler(message_store))
    processor.register_handler('1', TestRequestHandler(message_store))
    processor.register_handler('8', ExecutionReportHandler(message_store))
    processor.register_handler('D', NewOrderHandler(message_store))
    processor.register_handler('F', CancelOrderHandler(message_store))
    processor.register_handler('G', OrderCancelReplaceHandler(message_store))
    processor.register_handler('9', OrderCancelRejectHandler(message_store))
    processor.register_handler('AB', NewOrderMultilegHandler(message_store))
    processor.register_handler('AC', MultilegOrderCancelReplaceHandler(message_store))
    processor.register_handler('2', ResendRequestHandler(message_store))
    processor.register_handler('4', SequenceResetHandler(message_store))
    processor.register_handler('3', RejectHandler(message_store))
    processor.register_handler('5', LogoutHandler(message_store))

    # Example message processing
    logon_message = FixMessageFactory.create_message('A')  # Create logon message using factory
    execution_report_message = FixMessageFactory.create_message('8')  # Create execution report message using factory

    # Note: In real usage, these would be handled within an async context
    import asyncio
    asyncio.run(processor.process_message(logon_message))
    asyncio.run(processor.process_message(execution_report_message))
