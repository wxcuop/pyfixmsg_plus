import pytest
from unittest.mock import patch
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory

# Define a custom function to replace sort_values and _unmap
def debug_sort_values(msg, spec):
    tvals = list(msg.items())
    print("Message:", msg)
    print("Spec sorting keys:", spec.sorting_key)
    get_sorting_key = lambda x: spec.sorting_key.get(x[0], int(1e9 + x[0]))
    tvals.sort(key=get_sorting_key)
    return tvals

def debug_unmap(self, msg):
    print("Unmapping message:", msg)
    return debug_sort_values(msg, self.spec.msg_types[msg[35]])

@pytest.fixture
def spec(request):
    fname = request.config.getoption("--spec")
    if fname is None:
        raise ValueError("This test script needs to be invoked with the --spec argument, set to the path to the FIX50.xml file from quickfix.org")
    return FixSpec(xml_file=fname)

@pytest.fixture
def codec(spec):
    return Codec(spec=spec)

def test_fixmessagefactory_create_message(codec):
    FixMessageFactory.set_codec(codec)  # Set the codec
    with patch('pyfixmsg.codecs.stringfix.Codec._unmap', new=debug_unmap):
        message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
        print(message)
        assert message[35] == 'D'
        assert message[49] == 'SENDER'
        assert message[56] == 'TARGET'
        assert message['clordid'] == '12345'

def test_fixmessagefactory_return_message(codec):
    FixMessageFactory.set_codec(codec)  # Set the codec
    with patch('pyfixmsg.codecs.stringfix.Codec._unmap', new=debug_unmap):
        message = FixMessageFactory.create_message('D')
        FixMessageFactory.return_message(message)
        # Since the pool is internal, we can't assert directly, but we can ensure no exceptions are raised
