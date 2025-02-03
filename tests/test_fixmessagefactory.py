import pickle
from timeit import timeit
import datetime
import time
import sys
import os

import six
import pytest

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


from pyfixmsg_plus.fixengine.fixmessage_factory import FixMessageFactory
from pyfixmsg.reference import FixSpec
from pyfixmsg.codecs.stringfix import Codec


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


@pytest.fixture
def codec(spec):
    return Codec(spec=spec)


def test_fixmessagefactory_create_message(codec):
    FixMessageFactory.codec = codec  # Set the codec with spec
    message = FixMessageFactory.create_message('D', sender='SENDER', target='TARGET', clordid='12345')
    print(message)
    assert message[35] == 'D'
    assert message[49] == 'SENDER'
    assert message[56] == 'TARGET'
    assert message['clordid'] == '12345'


def test_fixmessagefactory_return_message(codec):
    FixMessageFactory.codec = codec  # Set the codec with spec
    message = FixMessageFactory.create_message('D')
    FixMessageFactory.return_message(message)
    # Since the pool is internal, we can't assert directly, but we can ensure no exceptions are raised
