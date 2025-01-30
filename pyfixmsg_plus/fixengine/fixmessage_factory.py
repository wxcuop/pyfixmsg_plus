from fixmessage_builder import FixMessageBuilder

class FixMessageFactory:
    @staticmethod
    def create_message(message_type, **kwargs):
        builder = FixMessageBuilder().set_msg_type(message_type).set_fields(**kwargs)
        if message_type == 'D':
            return builder.build()
        elif message_type == 'F':
            return builder.build()
        elif message_type == 'G':
            return builder.build()
        elif message_type == 'A':
            return builder.build()
        elif message_type == 'AB':
            return builder.build()
        elif message_type == 'AC':
            return builder.build()
        elif message_type == '8':
            return builder.build()
        elif message_type == '9':
            return builder.build()
        else:
            raise ValueError("Unknown message type")

# Usage example
# new_order_message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
