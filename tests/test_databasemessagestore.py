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

@pytest.mark.asyncio
async def test_store_message(db_store):
    await db_store.store_message('FIX.4.4', 'SENDER', 'TARGET', 1, 'Test message')
    result = await db_store.get_message('FIX.4.4', 'SENDER', 'TARGET', 1)
    assert result == 'Test message'

@pytest.mark.asyncio
async def test_sequence_numbers(db_store):
    await db_store.set_incoming_sequence_number(0)
    await db_store.set_outgoing_sequence_number(0)
    incoming_seqnum = db_store.get_next_incoming_sequence_number()
    outgoing_seqnum = db_store.get_next_outgoing_sequence_number()
    assert incoming_seqnum == 1
    assert outgoing_seqnum == 1
    await db_store.reset_sequence_numbers()
    await db_store.set_incoming_sequence_number(0)  # Reset to 0 for the test
    await db_store.set_outgoing_sequence_number(0)  # Reset to 0 for the test
    assert db_store.get_next_incoming_sequence_number() == 1
    assert db_store.get_next_outgoing_sequence_number() == 1
