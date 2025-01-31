from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

class FixMessageBuilder:
    def __init__(self, message=None):
        self.message = message or FixMessage()

    def set_version(self, version):
        self.message[8] = version
        return self

    def set_msg_type(self, msg_type):
        self.message[35] = msg_type
        return self

    def set_sender(self, sender):
        self.message[49] = sender
        return self

    def set_target(self, target):
        self.message[56] = target
        return self

    def set_sequence_number(self, seq_number):
        self.message[34] = seq_number
        return self

    def set_sending_time(self):
        self.message[52] = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        return self

    def set_custom_field(self, tag, value):
        self.message[tag] = value
        return self

    def build(self):
        return self.message
