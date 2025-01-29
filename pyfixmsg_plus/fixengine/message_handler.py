#Handle different message types with appropriate strategies (Strategy).
class MessageHandler:
    def handle(self, message):
        raise NotImplementedError

class LogonHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling logon message: {message}")

class ExecutionReportHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling execution report: {message}")

class NewOrderHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling new order: {message}")

class CancelOrderHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling cancel order: {message}")

class OrderCancelReplaceHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling order cancel/replace: {message}")

class OrderCancelRejectHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling order cancel reject: {message}")

class NewOrderMultilegHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling new order - multileg: {message}")

class MultilegOrderCancelReplaceHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling multileg order cancel/replace: {message}")

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

# Usage example for registering handlers:
# processor = MessageProcessor()
# processor.register_handler('A', LogonHandler())
# processor.register_handler('8', ExecutionReportHandler())
# processor.register_handler('D', NewOrderHandler())
# processor.register_handler('F', CancelOrderHandler())
# processor.register_handler('G', OrderCancelReplaceHandler())
# processor.register_handler('9', OrderCancelRejectHandler())
# processor.register_handler('AB', NewOrderMultilegHandler())
# processor.register_handler('AC', MultilegOrderCancelReplaceHandler())
