import pytest
from pyfixmsg_plus.fixengine.fixmessage_pool import FixMessagePool
from pyfixmsg.fixmessage import FixMessage, FixFragment

def test_fixmessagepool_get_message():
    pool = FixMessagePool(size=2)
    message1 = pool.get_message()
    message2 = pool.get_message()
    assert isinstance(message1, FixMessage)
    assert isinstance(message2, FixMessage)
    assert len(pool.available) == 0

def test_fixmessagepool_return_message():
    pool = FixMessagePool(size=2)
    message = pool.get_message()
    pool.return_message(message)
    assert len(pool.available) == 1
