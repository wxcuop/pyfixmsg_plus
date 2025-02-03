from datetime import datetime
from pyfixmsg_plus.fixengine.fixmessage_pool import FixMessagePool
from pyfixmsg import RepeatingGroup
from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.reference import FixSpec, FixTag
from pyfixmsg.codecs.stringfix import Codec

class FixMessageBuilder:
    def __init__(self, message=None, codec=None, fragment_class=None):
        self.message = message or FixMessage(codec=codec, fragment_class=fragment_class)
        self.codec = codec

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
        if self.codec:
            return self.codec.serialise(self.message)
        return self.message
