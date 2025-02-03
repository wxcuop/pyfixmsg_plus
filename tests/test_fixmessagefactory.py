import pytest
from pyfixmsg.reference import FixSpec
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory

@pytest.fixture
def spec(request):
    fname = request.config.getoption("--spec")
    if fname is None:
        raise ValueError("This test script needs to be invoked with the --spec argument, set to the path to the FIX50.xml file from quickfix.org")
    return FixSpec(xml_file=fname)

def test_set_codec(request):
    fname = request.config.getoption("--spec")
    FixMessageFactory.set_codec(fname)
    assert FixMessageFactory.codec is not None

def test_create_message(request):
    fname = request.config.getoption("--spec")
    FixMessageFactory.set_codec(fname)
    message = FixMessageFactory.create_message('D', {
        49='SENDER',   # SenderCompID
        56='TARGET',   # TargetCompID
        11='12345'     # ClOrdID
    })

    print(f"Message: {message}")
    
    assert message[35] == 'D'
    assert message[49] == 'SENDER'
    assert message[56] == 'TARGET'
    assert message[11] == '12345'

def test_return_message(request):
    fname = request.config.getoption("--spec")
    FixMessageFactory.set_codec(fname)
    message = FixMessageFactory.create_message('D')
    FixMessageFactory.return_message(message)
    assert True

def test_load_message(request):
    fname = request.config.getoption("--spec")
    FixMessageFactory.set_codec(fname)
    data = b'8=FIX.4.2|9=97|35=D|49=SENDER|56=TARGET|34=2|52=20220101-12:00:00|11=12345|21=1|40=2|54=1|10=128|'
    message = FixMessageFactory.load_message(data, separator='|')
    assert message[35] == 'D'
    assert message[49] == 'SENDER'
    assert message[56] == 'TARGET'
    assert message[11] == '12345'

if __name__ == "__main__":
    pytest.main(["--spec", "path/to/FIX50.xml"])
