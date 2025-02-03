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
        message = FixMessage()
        message[35] = message_type
        for tag, value in kwargs.items():
            message[tag] = value
        return message

    @staticmethod
    def load_message(data, separator='|'):
        if FixMessageFactory.codec is None:
            raise ValueError("FixMessageFactory.codec is not initialized. Call set_codec first.")
        message = FixMessage(codec=FixMessageFactory.codec, fragment_class=FixMessageFactory.fragment_class)
        message.load_fix(data, separator=separator)
        return message

    @staticmethod
    def create_message_from_dict(message_dict):
        if FixMessageFactory.codec is None:
            raise ValueError("FixMessageFactory.codec is not initialized. Call set_codec first.")
        message = FixMessage(codec=FixMessageFactory.codec, fragment_class=FixMessageFactory.fragment_class)
        for tag, value in message_dict.items():
            message[tag] = value
        return message

    @staticmethod
    def return_message(message):
        # Implement any cleanup or recycling logic if needed
        pass

    @staticmethod
    def fixmsg(*args, **kwargs):
        """
        Factory function. This allows us to keep the dictionary __init__
        arguments unchanged and force the codec to our given spec and avoid
        passing codec to serialisation and parsing methods.

        The codec defaults to a reasonable parser but without repeating groups.

        An alternative method is to use the ``to_wire`` and ``from_wire`` methods
        to serialise and parse messages and pass the codec explicitly.
        """
        if FixMessageFactory.codec is None:
            raise ValueError("FixMessageFactory.codec is not initialized. Call set_codec first.")
        returned = FixMessage(*args, **kwargs)
        returned.codec = FixMessageFactory.codec
        return returned
