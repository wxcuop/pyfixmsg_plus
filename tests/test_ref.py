from __future__ import print_function

import pickle
from timeit import timeit
import datetime
import time
import sys
import os

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


@pytest.fixture
def profiler(request):
    class CustomProfiler(object):
        def __init__(self, request):
            if request.config.getoption("--profile"):
                import cProfile
                self.profile = cProfile.Profile()
            else:
                self.profile = None

        def __enter__(self):
            if self.profile is None:
                return False
            self.profile.enable()

        def __exit__(self, *args, **kwargs):
            if self.profile is None:
                return False
            self.profile.disable()
            self.profile.dump_stats(request.function.__name__)
            return False

    return CustomProfiler(request)


class TestReference(object):
    def test_load(self, spec):
        assert len(spec.msg_types) > 0
        assert spec.msg_types.get(b'D') is not None
        assert 382 in spec.msg_types.get(b'8').groups

    def test_codec(self, spec):
        codec = Codec(spec=spec, decode_as='UTF-8')
        msg = (b'8=FIX.4.2;35=D;49=BLA;56=BLA;57=DEST;143=LN;11=eleven;18=1;21=2;54=2;40=2;59=0;55=PROD;'
               b'38=10;44=1;52=20110215-02:20:52.675;10=000;')
        res = codec.parse(msg, separator=';')
        assert {8: 'FIX.4.2',
                11: 'eleven',
                18: '1',
                21: '2',
                35: 'D',
                38: '10',
                40: '2',
                44: '1',
                49: 'BLA',
                52: '20110215-02:20:52.675',
                54: '2',
                55: 'PROD',
                56: 'BLA',
                57: 'DEST',
                59: '0',
                10: '000',
                143: 'LN'} == res
        codec = Codec(spec=spec)
        msg = (b'8=FIX.4.2;35=D;49=BLA;56=BLA;57=DEST;143=LN;11=eleven;18=1;21=2;54=2;40=2;59=0;55=PROD;'
               b'38=10;44=1;52=20110215-02:20:52.675;10=000;')
        res = codec.parse(msg, separator=';')
        assert {8: 'FIX.4.2',
                11: 'eleven',
                18: '1',
                21: '2',
                35: 'D',
                38: '10',
                40: '2',
                44: '1',
                49: 'BLA',
                52: '20110215-02:20:52.675',
                54: '2',
                55: 'PROD',
                56: 'BLA',
                57: 'DEST',
                59: '0',
                10: '000',
                143: 'LN'} == res

        codec = Codec(spec=spec, decode_all_as_347=True)
        res = codec.parse(msg, separator=';')
        assert {8: 'FIX.4.2',
                11: 'eleven',
                18: '1',
                21: '2',
                35: 'D',
                38: '10',
                40: '2',
                44: '1',
                49: 'BLA',
                52: '20110215-02:20:52.675',
                54: '2',
                55: 'PROD',
                56: 'BLA',
                57: 'DEST',
                59: '0',
                10: '000',
                143: 'LN'} == res
        msg = (b'8=FIX.4.2;35=D;49=BLA;56=BLA;57=DEST;347=UTF-8;143=LN;11=eleven;18=1;21=2;54=2;40=2;59=0;55=PROD;'
               b'38=10;44=1;52=20110215-02:20:52.675;10=000;')
        codec = Codec(spec=spec, decode_all_as_347=True)
        res = codec.parse(msg, separator=';')
        assert {8: 'FIX.4.2',
                11: 'eleven',
                18: '1',
                21: '2',
                35: 'D',
                38: '10',
                40: '2',
                44: '1',
                49: 'BLA',
                52: '20110215-02:20:52.675',
                54: '2',
                55: 'PROD',
                56: 'BLA',
                57: 'DEST',
                59: '0',
                10: '000',
                143: 'LN',
                347: 'UTF-8'} == res
        msg = (b'8=FIX.4.2;35=8;49=BLA;56=BLA;57=DEST;143=LN;11=eleven;18=1;21=2;54=2;40=2;59=0;55=PROD;'
               b'38=10;44=1;52=20110215-02:20:52.675;'
               b'382=2;'
               b'375=A;337=B;'
               b'375=B;437=B;'
               b'10=000;')
        codec = Codec(spec=spec)
        res = codec.parse(msg, separator=';')
        assert {8: 'FIX.4.2',
                11: 'eleven',
                382: [dict(((375, 'A'), (337, 'B'))),
                      dict(((375, 'B'), (437, 'B')))],
                18: '1',
                21: '2',
                35: '8',
                38: '10',
                40: '2',
                44: '1',
                49: 'BLA',
                52: '20110215-02:20:52.675',
                54: '2',
                55: 'PROD',
                56: 'BLA',
                57: 'DEST',
                59: '0',
                143: 'LN',
                10: '000'} == res
        # make sure that with a group finishing the message it still works
        msg = (b'8=FIX.4.2;35=8;49=BLA;56=BLA;57=DEST;143=LN;11=eleven;18=1;21=2;54=2;40=2;59=0;55=PROD;'
               b'38=10;44=1;52=20110215-02:20:52.675;'
               b'382=2;'
               b'375=A;337=B;'
               b'375=B;437=B;')

        res = codec.parse(msg, separator=';')
        assert {8: 'FIX.4.2',
                11: 'eleven',
                382: [dict(((375, 'A'), (337, 'B'))),
                      dict(((375, 'B'), (437, 'B')))],
                18: '1',
                21: '2',
                35: '8',
                38: '10',
                40: '2',
                44: '1',
                49: 'BLA',
                52: '20110215-02:20:52.675',
                54: '2',
                55: 'PROD',
                56: 'BLA',
                57: 'DEST',
                59: '0',
                143: 'LN',
                } == res

    def test_consecutive_rgroups(self, spec):
        codec = Codec(spec=spec, decode_as='UTF-8')
        msg = b'35=B;215=1;216=1;' \
              b'146=2;55=EURUSD;55=EURGBP;10=000;'
        msg = codec.parse(msg, separator=';')
        assert {35: 'B',
                215: [{216 : '1'}],
                146: [{55 : 'EURUSD'}, {55 : 'EURGBP'}],
                10: '000'
                } == msg
        lhs = tuple(codec._unmap(msg))
        assert lhs == ((35, 'B'),
                       (215, 1),
                       (216, '1'),
                       (146, 2),
                       (55, 'EURUSD'),
                       (55, 'EURGBP'),
                       (10, '000')
                       )
        serialised = '35=B;215=1;216=1;' \
                     '146=2;55=EURUSD;55=EURGBP;10=000;'.replace(';', chr(1)).encode('UTF-8')
        assert serialised == codec.serialise(msg)

    def test_nested_rgroup(self, spec):
        if 'FIX.4.4' not in spec.version and 'FIX5.' not in spec.version:
            # only relevant for fix 4.4 or above
            return
        codec = Codec(spec=spec, decode_as='UTF-8')
        msg = b'35=AE;555=1;687=AA;683=2;688=1;689=1;' \
              b'688=2;689=2;17807=11;10=000;'
        msg = codec.parse(msg, separator=';')
        assert {35: 'AE', 555: [
            dict(
                (
                    (687, 'AA'),
                    (683,
                     [
                         dict(((688, '1'), (689, '1'))),
                         dict(((688, '2'), (689, '2')))
                     ])
                )
            )
        ],
                17807: '11',
                10: '000'
                } == msg
        lhs = tuple(codec._unmap(msg))
        assert lhs == ((35, 'AE'),
                       (555, 1),
                       (687, 'AA'),
                       (683, 2),
                       (688, '1'),
                       (689, '1'),
                       (688, '2'),
                       (689, '2'),
                       (17807, '11'),
                       (10, '000')
                       )
        serialised = '35=AE;555=1;687=AA;683=2;688=1;689=1;' \
                     '688=2;689=2;17807=11;10=000;'.replace(';', chr(1)).encode('UTF-8')
        assert serialised == codec.serialise(msg)

    def test_empty_rgroups(self, spec):
        if 'FIX.4.4' not in spec.version and 'FIX5.' not in spec.version:
            # only relevant for fix 4.4 or above
            return
        codec = Codec(spec=spec, decode_as='UTF-8')
        msg = b'35=AJ;17807=11;232=2;233=bli;234=blu;' \
              b'233=blih;234=bluh;555=0;10=000;'
        msg = codec.parse(msg, separator=';')
        assert {35: 'AJ',
                17807: '11',
                232: [
                    {233: 'bli', 234: 'blu'},
                    {233: 'blih', 234: 'bluh'}
                ],
                555: [],
                10: '000'
                } == msg
        lhs = tuple(codec._unmap(msg))
        assert lhs == ((35, 'AJ'),
                       (232, 2),
                       (233, 'bli'),
                       (234, 'blu'),
                       (233, 'blih'),
                       (234, 'bluh'),
                       (555, 0),
                       (17807, '11'),
                       (10, '000')
                       )
        serialised = '35=AJ;232=2;233=bli;234=blu;233=blih;234=bluh;' \
                     '555=0;17807=11;10=000;'.replace(';', chr(1)).encode('UTF-8')
        assert serialised == codec.serialise(msg)

    def test_large_msg(self, spec, profiler):
        setup = """
import pyfixmsg.reference as ref
from pyfixmsg.codecs.stringfix import Codec
strfix = (
  b"8=FIX.4.2;9=1848;35=W;49=BBBBBBBB;56=XXXXXXX;34=2;52=20160418-15:44:37.238;115=YYYYYYYY;"
  b"142=NY;55=EURUSD;262=7357fbfc-057c-11e6-87de-ecf4bbc826fc;264=0;"
  b"268=20;"
  b"269=0;278=b1;270=1.13161;271=1000000;299=d1s30g1b1;1023=1;63=0;64=20160420;1070=0;"
  b"269=1;278=a1;270=1.1317;271=1000000;299=d1s30g1a1;1023=1;63=0;64=20160420;1070=0;"
  b"269=0;278=b2;270=1.13161;271=3000000;299=d1s30g1b2;1023=2;63=0;64=20160420;1070=0;"
  b"269=1;278=a2;270=1.1317;271=3000000;299=d1s30g1a2;1023=2;63=0;64=20160420;1070=0;"
  b"269=0;278=b3;270=1.13161;271=5000000;299=d1s30g1b3;1023=3;63=0;64=20160420;1070=0;"
  b"269=1;278=a3;270=1.1317;271=5000000;299=d1s30g1a3;1023=3;63=0;64=20160420;1070=0;"
  b"269=0;278=b4;270=1.13161;271=10000000;299=d1s30g1b4;1023=4;63=0;64=20160420;1070=0;"
  b"269=1;278=a4;270=1.1317;271=10000000;299=d1s30g1a4;1023=4;63=0;64=20160420;1070=0;"
  b"269=0;278=b5;270=1.13161;271=15000000;299=d1s30g1b5;1023=5;63=0;64=20160420;1070=0;"
  b"269=1;278=a5;270=1.1317;271=15000000;299=d1s30g1a5;1023=5;63=0;64=20160420;1070=0;"
  b"269=0;278=b6;270=1.13161;271=20000000;299=d1s30g1b6;1023=6;63=0;64=20160420;1070=0;"
  b"269=1;278=a6;270=1.1317;271=20000000;299=d1s30g1a6;1023=6;63=0;64=20160420;1070=0;"
  b"269=0;278=b7;270=1.13161;271=25000000;299=d1s30g1b7;1023=7;63=0;64=20160420;1070=0;"
  b"269=1;278=a7;270=1.1317;271=25000000;299=d1s30g1a7;1023=7;63=0;64=20160420;1070=0;"
  b"269=0;278=b8;270=1.13161;271=50000000;299=d1s30g1b8;1023=8;63=0;64=20160420;1070=0;"
  b"269=1;278=a8;270=1.1317;271=50000000;299=d1s30g1a8;1023=8;63=0;64=20160420;1070=0;"
  b"269=0;278=b9;270=1.13161;271=75000000;299=d1s30g1b9;1023=9;63=0;64=20160420;1070=0;"
  b"269=1;278=a9;270=1.1317;271=75000000;299=d1s30g1a9;1023=9;63=0;64
