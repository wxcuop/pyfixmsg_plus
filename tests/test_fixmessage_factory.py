import pytest
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory
from pyfixmsg.fixmessage import FixMessage

# Global variable to store the FIX specification
SPEC = None

@pytest.fixture(scope='module')
def setup_codec(request):
    global SPEC
    if SPEC is None:
        spec_file = request.config.getoption("--spec")
        if spec_file is None:
            pytest.fail("This test script needs to be invoked with the --spec argument set to the path to the FIX specification file.")
        FixMessageFactory.set_codec(spec_file)
        SPEC = FixMessageFactory.codec.spec

def test_set_codec(setup_codec):
    assert FixMessageFactory.codec is not None, "Codec should be initialized after calling set_codec"

def test_fixmsg_creation(setup_codec):
    msg = FixMessageFactory.fixmsg(35='D', ClOrdID='12345', Symbol='AAPL', Side='1', OrderQty='100', Price='150.00')
    assert isinstance(msg, FixMessage), "fixmsg should return an instance of FixMessage"
    assert msg[35] == 'D', "Message type should be 'D' for New Order Single"
    assert msg[11] == '12345', "ClOrdID should be '12345'"
    assert msg[55] == 'AAPL', "Symbol should be 'AAPL'"
    assert msg[54] == '1', "Side should be '1' (Buy)"
    assert msg[38] == '100', "OrderQty should be '100'"
    assert msg[44] == '150.00', "Price should be '150.00'"

def test_fixmsg_without_codec():
    FixMessageFactory.codec = None  # Ensure codec is not set
    with pytest.raises(ValueError, match="FixMessageFactory.codec is not initialized. Call set_codec first."):
        FixMessageFactory.fixmsg(35='D', ClOrdID='12345')

def test_fixmsg_serialization(setup_codec):
    msg = FixMessageFactory.fixmsg(35='D', ClOrdID='12345', Symbol='AAPL', Side='1', OrderQty='100', Price='150.00')
    serialized_message = msg.to_wire()
    assert isinstance(serialized_message, bytes), "Serialized message should be a bytestring"

def test_fixmsg_deserialization(setup_codec):
    raw_message = b'8=FIX.4.2|9=176|35=D|49=CLIENT|56=SERVER|34=1|52=20250330-00:44:51|11=12345|55=AAPL|54=1|38=100|44=150.00|10=128|'
    msg = FixMessageFactory.fixmsg().load_fix(raw_message, separator='|')
    assert isinstance(msg, FixMessage), "Deserialized message should be an instance of FixMessage"
    assert msg[35] == 'D', "Message type should be 'D' for New Order Single"
    assert msg[11] == '12345', "ClOrdID should be '12345'"
    assert msg[55] == 'AAPL', "Symbol should be 'AAPL'"
    assert msg[54] == '1', "Side should be '1' (Buy)"
    assert msg[38] == '100', "OrderQty should be '100'"
    assert msg[44] == '150.00', "Price should be '150.00'"

def pytest_addoption(parser):
    parser.addoption(
        "--spec", action="store", default=None, help="Path to the FIX specification file"
    )
