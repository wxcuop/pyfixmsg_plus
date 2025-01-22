import pytest
from fixsession import FixInitiator, FixAcceptor

@pytest.fixture
def mock_config(tmp_path):
    config_path = tmp_path / "config.ini"
    config_content = """
    [FIX]
    sender_comp_id = SENDER
    target_comp_id = TARGET
    host = localhost
    port = 5000
    use_tls = False
    heartbeat_interval = 30
    state_file = fix_session_state.json
    """
    config_path.write_text(config_content)
    return config_path

@pytest.fixture
def fix_initiator(mock_config):
    return FixInitiator(config_path=str(mock_config))

@pytest.fixture
def fix_acceptor(mock_config):
    return FixAcceptor(config_path=str(mock_config))

def test_fix_initiator_initialization(fix_initiator):
    assert fix_initiator.sender_comp_id == 'SENDER'
    assert fix_initiator.target_comp_id == 'TARGET'
    assert fix_initiator.host == 'localhost'
    assert fix_initiator.port == 5000
    assert fix_initiator.use_tls is False
    assert fix_initiator.heartbeat_interval == 30

def test_fix_acceptor_initialization(fix_acceptor):
    assert fix_acceptor.sender_comp_id == 'SENDER'
    assert fix_acceptor.target_comp_id == 'TARGET'
    assert fix_acceptor.host == 'localhost'
    assert fix_acceptor.port == 5000
    assert fix_acceptor.use_tls is False
    assert fix_acceptor.heartbeat_interval == 30
