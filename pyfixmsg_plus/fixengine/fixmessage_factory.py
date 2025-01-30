from fixmessage_builder import FixMessageBuilder

class FixMessageFactory:
    @staticmethod
    def create_message(message_type, **kwargs):
        if message_type == 'D':
            return FixMessageBuilder().set_msg_type('D').set_fields(**kwargs).build()
        elif message_type == 'F':
            return FixMessageBuilder().set_msg_type('F').set_fields(**kwargs).build()
        elif message_type == 'G':
            return FixMessageBuilder().set_msg_type('G').set_fields(**kwargs).build()
        elif message_type == 'A':
            return FixMessageBuilder().set_msg_type('A').set_fields(**kwargs).build()
        elif message_type == 'AB':
            return FixMessageBuilder().set_msg_type('AB').set_fields(**kwargs).build()
        elif message_type == 'AC':
            return FixMessageBuilder().set_msg_type('AC').set_fields(**kwargs).build()
        elif message_type == '8':
            return FixMessageBuilder().set_msg_type('8').set_fields(**kwargs).build()
        elif message_type == '9':
            return FixMessageBuilder().set_msg_type('9').set_fields(**kwargs).build()
        else:
            raise ValueError("Unknown message type")

# Usage example
# new_order_message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
