from fixmessage_builder import FixMessageBuilder

class FixMessageFactory:
    @staticmethod
    def create_message(message_type, **kwargs):
        builder = FixMessageBuilder().set_msg_type(message_type)
        for tag, value in kwargs.items():
            builder.set_custom_field(tag, value)
        
        return builder.build()

# Usage example
# new_order_message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
