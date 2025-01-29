class MessageHandler:
    def handle(self, message):
        raise NotImplementedError

class LogonHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling logon message: {message}")

class ExecutionReportHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling execution report: {message}")

class MessageProcessor:
    def __init__(self):
        self.handlers = {}

    def register_handler(self, message_type, handler):
        self.handlers[message_type] = handler

    def process_message(self, message):
        message_type = message.get(35)  # Assuming tag 35 is the message type
        handler = self.handlers.get(message_type)
        if handler:
            handler.handle(message)
        else:
            print(f"No handler for message type: {message_type}")

# Usage example
# processor = MessageProcessor()
# processor.register_handler('A', LogonHandler())
# processor.register_handler('8', ExecutionReportHandler())
# processor.process_message(logon_message)
# processor.process_message(execution_report_message)
