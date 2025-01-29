#Handle different message types with appropriate strategies (Strategy).
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
    def handle(self, message):
        raise NotImplementedError

# Concrete implementations of message handlers with logging decorator
class LogonHandler(MessageHandler):
    @logging_decorator
    def handle(self, message):
        print(f"Handling logon message: {message}")

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

# MessageProcessor to register and process different message handlers
class MessageProcessor:
    def __init__(self):
        self.handlers = {}

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
    processor = MessageProcessor()
    processor.register_handler('A', LogonHandler())
    processor.register_handler('8', ExecutionReportHandler())
    processor.register_handler('D', NewOrderHandler())
    processor.register_handler('F', CancelOrderHandler())
    processor.register_handler('G', OrderCancelReplaceHandler())
    processor.register_handler('9', OrderCancelRejectHandler())
    processor.register_handler('AB', NewOrderMultilegHandler())
    processor.register_handler('AC', MultilegOrderCancelReplaceHandler())

    # Example message processing
    logon_message = FixMessage()
    logon_message.set_field(35, 'A')  # Message type 'A'
    execution_report_message = FixMessage()
    execution_report_message.set_field(35, '8')  # Message type '8'

    # Note: In real usage, these would be handled within an async context
    import asyncio
    asyncio.run(processor.process_message(logon_message))
    asyncio.run(processor.process_message(execution_report_message))
