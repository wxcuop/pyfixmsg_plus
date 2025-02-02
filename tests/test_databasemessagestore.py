import pytest
import os
from pyfixmsg_plus.fixengine.database_message_store import DatabaseMessageStore

@pytest.fixture
def db_path(tmp_path):
    return os.path.join(tmp_path, "test.db")

@pytest.fixture
def db_store(db_path):
    store = DatabaseMessageStore(db_path)
    store.beginstring = 'FIX.4.4'
    store.sendercompid = 'SENDER'
    store.targetcompid = 'TARGET'
    return store

def test_store_message(db_store):
    db_store.store_message('FIX.4.4', 'SENDER', 'TARGET', 1, 'Test message')
    assert db_store.get_message('FIX.4.4', 'SENDER', 'TARGET', 1) == 'Test message'

def test_sequence_numbers(db_store):
    db_store.set_incoming_sequence_number(0)
    db_store.set_outgoing_sequence_number(0)
    incoming_seqnum = db_store.get_next_incoming_sequence_number()
    outgoing_seqnum = db_store.get_next_outgoing_sequence_number()
    assert incoming_seqnum == 1
    assert outgoing_seqnum == 1
    db_store.reset_sequence_numbers()
    assert db_store.get_next_incoming_sequence_number() == 1
    assert db_store.get_next_outgoing_sequence_number() == 1
