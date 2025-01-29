class MessageHandler:
    def handle(self, message):
        raise NotImplementedError

class LogonHandler(MessageHandler):
    def handle(self, message):
        print(f"Handling logon message: {message}")

class LoggingDecorator(MessageHandler):
    def __init__(self, handler):
        self.handler = handler

    def handle(self, message):
        print(f"Logging message before handling: {message}")
        self.handler.handle(message)
        print(f"Logging message after handling: {message}")

# Usage example
# logon_handler = LogonHandler()
# decorated_handler = LoggingDecorator(logon_handler)
# decorated_handler.handle(logon_message)
