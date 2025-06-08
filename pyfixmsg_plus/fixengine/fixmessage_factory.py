from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg.codecs.stringfix import Codec

class FixMessageFactory:
    """
    Factory class for creating FIX messages.
    """

    @staticmethod
    def create_message(msg_type, codec=None):
        """
        Creates a FIX message with the specified type.

        Args:
            msg_type (str): The FIX message type (e.g., 'A' for Logon, '1' for TestRequest).
            codec (Codec, optional): The codec to use for message serialization.

        Returns:
            FixMessage: A new FIX message with the specified type populated.
        """
        message = FixMessage()
        message[35] = msg_type  # MsgType
        message.codec = codec or Codec()  # Use provided codec or default
        return message

    @staticmethod
    def create_logon_message(sender, target, seq_num, codec=None):
        """
        Creates a Logon FIX message.

        Args:
            sender (str): SenderCompID.
            target (str): TargetCompID.
            seq_num (int): MsgSeqNum.
            codec (Codec, optional): The codec to use for message serialization.

        Returns:
            FixMessage: A Logon FIX message.
        """
        message = FixMessageFactory.create_message('A', codec)  # Logon MsgType
        message[49] = sender  # SenderCompID
        message[56] = target  # TargetCompID
        message[34] = seq_num  # MsgSeqNum
        return message

    @staticmethod
    def create_heartbeat_message(codec=None):
        """
        Creates a Heartbeat FIX message.

        Args:
            codec (Codec, optional): The codec to use for message serialization.

        Returns:
            FixMessage: A Heartbeat FIX message.
        """
        return FixMessageFactory.create_message('0', codec)  # Heartbeat MsgType

    @staticmethod
    def create_test_request_message(sender, target, test_req_id, codec=None):
        """
        Creates a TestRequest FIX message.

        Args:
            sender (str): SenderCompID.
            target (str): TargetCompID.
            test_req_id (str): TestReqID.
            codec (Codec, optional): The codec to use for message serialization.

        Returns:
            FixMessage: A TestRequest FIX message.
        """
        message = FixMessageFactory.create_message('1', codec)  # TestRequest MsgType
        message[49] = sender  # SenderCompID
        message[56] = target  # TargetCompID
        message[112] = test_req_id  # TestReqID
        return message

    @staticmethod
    def create_message_with_repeating_group(msg_type, group_data, codec=None):
        """
        Creates a FIX message with a repeating group.

        Args:
            msg_type (str): The FIX message type.
            group_data (dict): Data for the repeating group, where the key is the group tag and the value is a list
                               of FixFragment objects.
            codec (Codec, optional): The codec to use for message serialization.

        Returns:
            FixMessage: A FIX message with the specified repeating group.
        """
        message = FixMessageFactory.create_message(msg_type, codec)
        for group_tag, fragments in group_data.items():
            repeating_group = []
            for fragment_data in fragments:
                fragment = FixFragment(fragment_data)
                repeating_group.append(fragment)
            message[group_tag] = repeating_group
        return message

    @staticmethod
    def validate_message(message):
        """
        Validates the contents of a FIX message.

        Args:
            message (FixMessage): The FIX message to validate.

        Returns:
            bool: True if the message is valid, False otherwise.
        """
        required_tags = [35, 49, 56, 34]  # MsgType, SenderCompID, TargetCompID, MsgSeqNum
        for tag in required_tags:
            if tag not in message:
                raise ValueError(f"Missing required tag: {tag}")
        return True
