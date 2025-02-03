from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec

class FixMessageFactory:
    codec = None
    fragment_class = FixFragment

    @staticmethod
    def set_codec(spec_file):
        spec = FixSpec(spec_file)
        FixMessageFactory.codec = Codec(spec=spec, fragment_class=FixMessageFactory.fragment_class)

    @staticmethod
    def create_message(message_type, **kwargs):
        if FixMessageFactory.codec is None:
            raise ValueError("FixMessageFactory.codec is not initialized. Call set_codec first.")
        message = FixMessage(codec=FixMessageFactory.codec, fragment_class=FixMessageFactory.fragment_class)
        message[35] = message_type
        for tag, value in kwargs.items():
            message[tag] = value
            
        return message

    @staticmethod
    def return_message(message):
        # If required, implement logic to handle returned messages
        pass
