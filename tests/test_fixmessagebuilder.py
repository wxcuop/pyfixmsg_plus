import pytest
from pyfixmsg_plus.fixengine.fixmessage_builder import FixMessageBuilder
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg.fixmessage import FixMessage
from pyfixmsg.reference import FixSpec

SPEC = None

@pytest.fixture
def spec(request):
    global SPEC
    if SPEC is None:
        fname = request.config.getoption("--spec")
        if fname is None:
            pytest.fail("""

            This test script needs to be invoked with the --spec
            argument, set to the path to the FIX50.xml file from quickfix.org

            """)
        SPEC = FixSpec(xml_file=fname)
    return SPEC

# Mock ConfigManager
class MockConfigManager:
    def __init__(self, spec_path):
        self.spec_path = spec_path

    def get(self, section, option, fallback):
        if section == 'FIX' and option == 'spec_path':
            return self.spec_path
        return fallback

@pytest.fixture
def fix_message_builder(spec, request):
    config_manager = MockConfigManager(request.config.getoption("--spec"))
    return FixMessageBuilder(config_manager)

def test_set_version(fix_message_builder):
    print(dir(spec))
    fix_message_builder.set_version('FIX.4.2')
    assert fix_message_builder.get_message()['BeginString'] == 'FIX.4.2'

# def test_set_msg_type(fix_message_builder):
#     fix_message_builder.set_msg_type('D')
#     assert fix_message_builder.get_message()['MsgType'] == 'D'

# def test_set_sender(fix_message_builder):
#     fix_message_builder.set_sender('SENDER')
#     assert fix_message_builder.get_message()['SenderCompID'] == 'SENDER'

# def test_set_target(fix_message_builder):
#     fix_message_builder.set_target('TARGET')
#     assert fix_message_builder.get_message()['TargetCompID'] == 'TARGET'

# def test_set_sequence_number(fix_message_builder):
#     fix_message_builder.set_sequence_number(1)
#     assert fix_message_builder.get_message()['MsgSeqNum'] == 1

# def test_set_sending_time(fix_message_builder):
#     fix_message_builder.set_sending_time()
#     assert 'SendingTime' in fix_message_builder.get_message()

# def test_set_fixtag(fix_message_builder):
#     fix_message_builder.set_fixtag(9999, 'TEST')
#     assert fix_message_builder.get_message()[9999] == 'TEST'

# def test_set_fixtag_by_name(fix_message_builder):
#     fix_message_builder.set_fixtag_by_name('SenderCompID', 'SENDER')
#     assert fix_message_builder.get_message()['SenderCompID'] == 'SENDER'

# def test_set_direction(fix_message_builder):
#     fix_message_builder.set_direction('OUT')
#     assert fix_message_builder.get_message().direction == 'OUT'

# def test_set_recipient(fix_message_builder):
#     fix_message_builder.set_recipient('RECIPIENT')
#     assert fix_message_builder.get_message().recipient == 'RECIPIENT'

# def test_build(fix_message_builder):
#     fix_message_builder.set_version('FIX.4.2')
#     assert '8=FIX.4.2' in fix_message_builder.build()

# def test_update_message(fix_message_builder):
#     fix_message_builder.update_message({'SenderCompID': 'SENDER'})
#     assert fix_message_builder.get_message()['SenderCompID'] == 'SENDER'

# def test_reset_message(fix_message_builder):
#     fix_message_builder.set_version('FIX.4.2')
#     fix_message_builder.reset_message()
#     assert 'BeginString' not in fix_message_builder.get_message()
