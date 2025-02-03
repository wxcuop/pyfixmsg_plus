import pytest
from pyfixmsg_plus.fixengine.fixmessage_pool import FixMessagePool
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec

@pytest.fixture
def spec(request):
    fname = request.config.getoption("--spec")
    if fname is None:
        raise ValueError("This test script needs to be invoked with the --spec argument, set to the path to the FIX50.xml file from quickfix.org")
    return FixSpec(xml_file=fname)

@pytest.fixture
def codec(spec):
    return Codec(spec=spec)

def test_fixmessagepool_get_message(codec):
    pool = FixMessagePool(size=20, codec=codec)
    message = pool.get_message()
    assert message is not None

def test_fixmessagepool_return_message(codec):
    pool = FixMessagePool(size=20, codec=codec)
    message = pool.get_message()
    pool.return_message(message)
    assert len(pool.pool) == 20
