from fixmessage_builder import FixMessageBuilder

class FixMessageFactory:
    @staticmethod
    def create_message(message_type, **kwargs):
        if message_type == 'D':
            return FixMessageBuilder().set_msg_type('D').set_fields(**kwargs).build()
        elif message_type == '8':
            return FixMessageBuilder().set_msg_type('8').set_fields(**kwargs).build()
        # Add other message types as needed
        else:
            raise ValueError("Unknown message type")

# Usage example
# new_order_message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
