from pyfixmsg.fixmessage import FixMessage
import datetime
from pyfixmsg.codecs.stringfix import Codec
from pyfixmsg_plus.fixengine.configmanager import ConfigManager

class FixMessagePool:
    def __init__(self, config_manager):
        fix_spec_path = config_manager.get('FIX', 'spec_path', 'path/to/default/spec.xml')
        self.codec = Codec(spec=fix_spec_path)
        size = int(config_manager.get('POOL', 'size', 20))
        self.pool = [FixMessage(codec=self.codec) for _ in range(size)]

    def get_message(self):
        if not self.pool:
            message = FixMessage(codec=self.codec)
        else:
            message = self.pool.pop()
        message.time = datetime.datetime.utcnow()  # Update the time
        return message

    def return_message(self, message):
        self.pool.append(message)

# Usage example
# config_manager = ConfigManager()
# pool = FixMessagePool(config_manager=config_manager)
