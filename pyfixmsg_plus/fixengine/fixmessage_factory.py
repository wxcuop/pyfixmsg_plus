from .fixmessage_builder import FixMessageBuilder
from .fixmessage_pool import FixMessagePool

class FixMessageFactory:
    pool = None
    codec = None  # Add a codec attribute
    fragment_class = None  # Add a fragment_class attribute

    @staticmethod
    def set_codec(codec, fragment_class=None):
        FixMessageFactory.codec = codec
        FixMessageFactory.fragment_class = fragment_class
        FixMessageFactory.pool = FixMessagePool(size=20, codec=codec, fragment_class=fragment_class)  # Initialize pool with codec and fragment_class

    @staticmethod
    def create_message(message_type, **kwargs):
        if FixMessageFactory.pool is None:
            raise ValueError("FixMessageFactory.pool is not initialized. Call set_codec first.")
        message = FixMessageFactory.pool.get_message()
        builder = FixMessageBuilder(message, codec=FixMessageFactory.codec, fragment_class=FixMessageFactory.fragment_class).set_msg_type(message_type)
        for tag, value in kwargs.items():
            builder.set_custom_field(tag, value)
        
        return builder.build()

    @staticmethod
    def return_message(message):
        if FixMessageFactory.pool is None:
            raise ValueError("FixMessageFactory.pool is not initialized. Call set_codec first.")
        FixMessageFactory.pool.return_message(message)
