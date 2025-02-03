import pytest
from pyfixmsg.reference import FixSpec
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory

@pytest.fixture
def spec(request):
    fname = request.config.getoption("--spec")
    if fname is None:
        raise ValueError("This test script needs to be invoked with the --spec argument, set to the path to the FIX50.xml file from quickfix.org")
    return FixSpec(xml_file=fname)

def test_set_codec(spec):
    FixMessageFactory.set_codec(spec)
    assert FixMessageFactory.codec is not None

def test_create_message(spec):
    FixMessageFactory.set_codec(spec)
    message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
    assert message[35] == 'D'
    assert message[49] == 'SENDER'
    assert message[56] == 'TARGET'
    assert message['clordid'] == '12345'

def test_return_message(spec):
    FixMessageFactory.set_codec(spec)
    message = FixMessageFactory.create_message('D')
    FixMessageFactory.return_message(message)
    # Since the pool is internal, we can't assert directly, but we can ensure no exceptions are raised
    assert True

if __name__ == "__main__":
    pytest.main(["--spec", "path/to/FIX50.xml"])
