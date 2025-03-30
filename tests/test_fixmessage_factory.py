from __future__ import print_function
from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory
from pyfixmsg.fixmessage import FixMessage

import pickle
from timeit import timeit
import datetime
import time
import sys
import os

import six
import pytest

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec
from pyfixmsg.fixmessage import FixMessage, FixFragment
from pyfixmsg import RepeatingGroup, len_and_chsum

SPEC = None


@pytest.fixture
def spec(request):
    global SPEC
    if SPEC is None:
        fname = request.config.getoption("--spec")
        if fname is None:
            print("""

      This test script needs to be invoked with the --spec
      argument, set to the path to the FIX50.xml file from quickfix.org

      """)
        SPEC = FixSpec(xml_file=fname)
    return SPEC

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
    msg = FixMessageFactory.fixmsg()
    msg.update({35: 'D', 11: '12345', 55: 'AAPL', 54: '1', 38: '100', 44: '150.00'})
    assert isinstance(msg, FixMessage), "fixmsg should return an instance of FixMessage"
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
