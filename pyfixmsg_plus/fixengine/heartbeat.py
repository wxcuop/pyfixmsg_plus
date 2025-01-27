import threading
import time
from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

class Heartbeat:
    def __init__(self, send_message, interval=30):
        self.send_message = send_message
        self.interval = interval
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._send_heartbeat)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _send_heartbeat(self):
        while self.running:
            message = FixMessage()
            message.update({
                8: 'FIX.4.4',
                35: '0',  # Heartbeat
                49: 'SERVER',
                56: 'CLIENT',
                34: 1,  # This should be dynamically set
                52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            })
            self.send_message(message)
            time.sleep(self.interval)
