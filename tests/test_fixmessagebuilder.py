import pytest
from pyfixmsg_plus.fixengine.fixmessage_builder import FixMessageBuilder

def test_fixmessagebuilder_set_version():
    builder = FixMessageBuilder()
    message = builder.set_version('FIX.4.4').build()
    assert message[8] == 'FIX.4.4'

def test_fixmessagebuilder_set_msg_type():
    builder = FixMessageBuilder()
    message = builder.set_msg_type('D').build()
    assert message[35] == 'D'

def test_fixmessagebuilder_set_sender():
    builder = FixMessageBuilder()
    message = builder.set_sender('SENDER').build()
    assert message[49] == 'SENDER'

def test_fixmessagebuilder_set_target():
    builder = FixMessageBuilder()
    message = builder.set_target('TARGET').build()
    assert message[56] == 'TARGET'

def test_fixmessagebuilder_set_sequence_number():
    builder = FixMessageBuilder()
    message = builder.set_sequence_number(1).build()
    assert message[34] == 1

def test_fixmessagebuilder_set_sending_time():
    builder = FixMessageBuilder()
    message = builder.set_sending_time().build()
    assert 52 in message

def test_fixmessagebuilder_set_custom_field():
    builder = FixMessageBuilder()
    message = builder.set_custom_field(9999, 'CustomValue').build()
    assert message[9999] == 'CustomValue'
