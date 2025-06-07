from pyfixmsg.fixmessage import FixMessage

class FixMessageFactory:
    """
    Factory class for creating FIX messages.
    """

    @staticmethod
    def create_message(msg_type):
        """
        Creates a FIX message with the specified type.

        Args:
            msg_type (str): The FIX message type (e.g., 'A' for Logon, '1' for TestRequest).

        Returns:
            FixMessage: A new FIX message with the specified type populated.
        """
        message = FixMessage()
        message[35] = msg_type  # MsgType
        return message

    @staticmethod
    def create_logon_message(sender, target, seq_num):
        """
        Creates a Logon FIX message.

        Args:
            sender (str): SenderCompID.
            target (str): TargetCompID.
            seq_num (int): MsgSeqNum.

        Returns:
            FixMessage: A Logon FIX message.
        """
        message = FixMessageFactory.create_message('A')  # Logon MsgType
        message[49] = sender  # SenderCompID
        message[56] = target  # TargetCompID
        message[34] = seq_num  # MsgSeqNum
        return message

    @staticmethod
    def create_heartbeat_message():
        """
        Creates a Heartbeat FIX message.

        Returns:
            FixMessage: A Heartbeat FIX message.
        """
        return FixMessageFactory.create_message('0')  # Heartbeat MsgType

    @staticmethod
    def create_test_request_message(sender, target, test_req_id):
        """
        Creates a TestRequest FIX message.

        Args:
            sender (str): SenderCompID.
            target (str): TargetCompID.
            test_req_id (str): TestReqID.

        Returns:
            FixMessage: A TestRequest FIX message.
        """
        message = FixMessageFactory.create_message('1')  # TestRequest MsgType
        message[49] = sender  # SenderCompID
        message[56] = target  # TargetCompID
        message[112] = test_req_id  # TestReqID
        return message