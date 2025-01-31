from fixmessage_builder import FixMessageBuilder
from fixmessage_pool import FixMessagePool

class FixMessageFactory:
    pool = FixMessagePool(size=20)  # Adjust pool size based on expected load

    @staticmethod
    def create_message(message_type, **kwargs):
        message = FixMessageFactory.pool.get_message()
        builder = FixMessageBuilder(message).set_msg_type(message_type)
        for tag, value in kwargs.items():
            builder.set_custom_field(tag, value)
        
        return builder.build()

    @staticmethod
    def return_message(message):
        FixMessageFactory.pool.return_message(message)

# Usage example
# factory = FixMessageFactory()
# new_order_message = factory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
# factory.return_message(new_order_message)
