import pytest
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory

def test_fixmessagefactory_create_message():
    message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
    print(message)  # Debug: Print the created message to inspect its contents
    assert message[35] == 'D'
    assert message[49] == 'SENDER'
    assert message[56] == 'TARGET'
    assert message['clordid'] == '12345'

def test_fixmessagefactory_return_message():
    message = FixMessageFactory.create_message('D')
    FixMessageFactory.return_message(message)
    # Since the pool is internal, we can't assert directly, but we can ensure no exceptions are raised
