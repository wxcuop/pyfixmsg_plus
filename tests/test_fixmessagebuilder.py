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
    tag_name = 'BeginString'
    tag_number = fix_message_builder.fix_spec.tags.by_name(tag_name).tag
    print(f"Tag name: {tag_name}, Tag number: {tag_number}")
    print(fix_message_builder.get_message().output_fix())
