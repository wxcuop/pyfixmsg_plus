from .fixmessage_builder import FixMessageBuilder
from .fixmessage_pool import FixMessagePool

class FixMessageFactory:
    pool = FixMessagePool(size=20)  # Adjust pool size based on expected load
    codec = None  # Add a codec attribute

    @staticmethod
    def set_codec(codec):
        FixMessageFactory.codec = codec  # Method to set the codec

    @staticmethod
    def create_message(message_type, **kwargs):
        message = FixMessageFactory.pool.get_message()
        builder = FixMessageBuilder(message, codec=FixMessageFactory.codec).set_msg_type(message_type)  # Pass the codec to the builder
        for tag, value in kwargs.items():
            builder.set_custom_field(tag, value)
        
        return builder.build()

    @staticmethod
    def return_message(message):
        FixMessageFactory.pool.return_message(message)

# Usage example
# factory = FixMessageFactory()
# factory.set_codec(your_codec)
# new_order_message = factory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
# factory.return_message(new_order_message)
