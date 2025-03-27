from datetime import datetime
from pyfixmsg_plus.fixengine.fixmessage_pool import FixMessagePool
from pyfixmsg import RepeatingGroup
from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.reference import FixSpec, FixTag
from pyfixmsg.codecs.stringfix import Codec
from pyfixmsg_plus.fixengine.configmanager import ConfigManager  # Import ConfigManager

class FixMessageBuilder:
    def __init__(self, config_manager):
        fix_spec_path = config_manager.get('FIX', 'spec_path', 'path/to/default/spec.xml')
        print(fix_spec_path)
        self.fix_spec = FixSpec(fix_spec_path)
        self.codec = Codec(spec=self.fix_spec)
        self.message = FixMessage(codec=self.codec)

    def set_version(self, version):
        return self.set_fixtag_by_name('BeginString', version)
    
    def set_msg_type(self, msg_type):
        return self.set_fixtag_by_name('MsgType', msg_type)
    
    def set_sender(self, sender):
        return self.set_fixtag_by_name('SenderCompID', sender)
    
    def set_target(self, target):
        return self.set_fixtag_by_name('TargetCompID', target)
    
    def set_sequence_number(self, seq_number):
        return self.set_fixtag_by_name('MsgSeqNum', seq_number)
    
    def set_sending_time(self):
        sending_time = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        return self.set_fixtag_by_name('SendingTime', sending_time)

    def set_fixtag(self, tag, value):
        self.message[tag] = value
        return self
    
    def set_fixtag_by_name(self, tag_name, value):
        tag_number = self.fix_spec.tags.by_name(tag_name).tag
        if tag_number is not None:
            self.message[tag_number] = str(value)
        else:
            raise ValueError(f"Tag name '{tag_name}' not found in FixSpec.")
        return self

    def set_direction(self, direction):
        self.message.direction = direction
        return self

    def set_recipient(self, recipient):
        self.message.recipient = recipient
        return self

    def build(self):
        if self.codec:
            return self.codec.serialise(self.message)
        return self.message
    
    def get_message(self):
        return self.message
    
    def update_message(self, tags_dict):
        self.message.update(tags_dict)
        return self
    
    def reset_message(self):
        self.message = FixMessage(codec=self.codec)
        return self

class FixMessageDecoder:
    def __init__(self, config_manager):
        fix_spec_path = config_manager.get('FIX', 'spec_path', 'path/to/default/spec.xml')
        self.fix_spec = FixSpec(fix_spec_path)
        self.codec = Codec(spec=self.fix_spec)

    def decode(self, raw_message):
        """Decode a raw FIX message."""
        decoded_message = FixMessage.from_buffer(raw_message, self.codec)
        return decoded_message
