from .fixmessage_builder import FixMessageBuilder
from .fixmessage_pool import FixMessagePool

class FixMessageFactory:
    pool = None
    codec = None  # Add a codec attribute

    @staticmethod
    def set_codec(codec):
        FixMessageFactory.codec = codec
        FixMessageFactory.pool = FixMessagePool(size=20, codec=codec)  # Initialize pool with codec

    @staticmethod
    def create_message(message_type, **kwargs):
        message = FixMessageFactory.pool.get_message()
        builder = FixMessageBuilder(message, codec=FixMessageFactory.codec).set_msg_type(message_type)
        for tag, value in kwargs.items():
            builder.set_custom_field(tag, value)
        
        return builder.build()

    @staticmethod
    def return_message(message):
        FixMessageFactory.pool.return_message(message)
