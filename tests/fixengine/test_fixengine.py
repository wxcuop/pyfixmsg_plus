# test_fixengine.py

import asyncio
import pytest
from pyfixmsg_plus.fixengine.engine import FixEngine

# Dummy implementation of the Application abstract class
class DummyApplication:
    async def onLogon(self, message):
        # Simulate processing a logon message
        pass

    async def onMessage(self, message):
        # Simulate processing a generic message
        pass

    def onCreate(self, sessionID):
        # Simulate creation logic
        pass

    def onLogout(self, sessionID):
        # Simulate logout logic
        pass

    def toAdmin(self, message, sessionID):
        # Process message to be sent to admin
        pass

    def fromAdmin(self, message, sessionID):
        # Process message coming from admin
        pass

    def toApp(self, message, sessionID):
        # Process message before sending to application
        pass

    def fromApp(self, message, sessionID):
        # Process message after receiving from application
        pass

# Dummy network implementation to capture sent messages and simulate minimal behavior
class DummyNetwork:
    def __init__(self):
        self.sent_messages = []

    async def send(self, message):
        # Instead of sending over the network, store the message
        self.sent_messages.append(message)

    async def receive(self):
        # Simulate a short delay and no data received
        await asyncio.sleep(0.01)
        return b""

    def set_transport(self, reader, writer):
        # Dummy implementation; no transport setup
        pass

    async def connect(self):
        # Simulate successful connection
        pass

    async def start_accepting(self, callback):
        # Simulate starting to accept connections
        pass

    async def disconnect(self):
        # Simulate disconnect
        pass

# Dummy message store to track sequence numbers and stored messages
class DummyMessageStore:
    def __init__(self):
        self.outgoing_seq = 1
        self.incoming_seq = 1
        self.stored_messages = []

    def get_next_outgoing_sequence_number(self):
        val = self.outgoing_seq
        self.outgoing_seq += 1
        return val

    def get_next_incoming_sequence_number(self):
        return self.incoming_seq

    def set_incoming_sequence_number(self, seq):
        self.incoming_seq = seq

    def set_outgoing_sequence_number(self, seq):
        self.outgoing_seq = seq

    def store_message(self, beginstring, sender, target, seqnum, message):
        self.stored_messages.append((seqnum, message))

    def reset_sequence_numbers(self):
        self.outgoing_seq = 1
        self.incoming_seq = 1

# Dummy configuration manager that returns fixed values for testing
class DummyConfigManager:
    def get(self, section, option, default=None):
        config_mapping = {
            ('FIX', 'host'): '127.0.0.1',
            ('FIX', 'port'): '5000',
            ('FIX', 'sender'): 'SENDER',
            ('FIX', 'target'): 'TARGET',
            ('FIX', 'version'): 'FIX.4.4',
            ('FIX', 'use_tls'): 'false',
            ('FIX', 'mode'): 'initiator',
            ('FIX', 'state_file'): 'dummy.db',
            ('FIX', 'heartbeat_interval'): '30',
            ('FIX', 'retry_interval'): '1',  # Shorter interval for testing
            ('FIX', 'max_retries'): '3'
        }
        return config_mapping.get((section, option), default)

@pytest.fixture
def fix_engine(monkeypatch):
    # Create a dummy application instance that satisfies the Application API
    app = DummyApplication()
    config_manager = DummyConfigManager()
    engine = FixEngine(config_manager, app)
    
    # Override the network and message_store with our dummy objects
    dummy_network = DummyNetwork()
    dummy_message_store = DummyMessageStore()
    engine.network = dummy_network
    engine.message_store = dummy_message_store
    return engine

@pytest.mark.asyncio
async def test_send_message(fix_engine):
    # Create a dummy FIX message dictionary.
    # Note: The engine's send_message method uses FixMessageFactory internally,
    # so this dictionary should contain minimal header info, such as tag 35 (message type)
    # and sender/target identifiers.
    message = {'35': 'A', '49': 'SENDER', '56': 'TARGET'}
    
    # Capture the current outgoing sequence number before sending.
    seq_before = fix_engine.message_store.outgoing_seq
    
    # Call send_message; this is an async method.
    await fix_engine.send_message(message)
    
    # Verify that the dummy message store now has one stored message.
    assert len(fix_engine.message_store.stored_messages) == 1
    stored_seq, stored_msg = fix_engine.message_store.stored_messages[0]
    
    # The stored sequence number should match the one before sending the message.
    assert stored_seq == seq_before
    
    # Verify that our dummy network has at least one sent message.
    assert len(fix_engine.network.sent_messages) == 1

@pytest.mark.asyncio
async def test_reset_sequence_numbers(fix_engine):
    # Set non-default sequence numbers.
    fix_engine.message_store.outgoing_seq = 10
    fix_engine.message_store.incoming_seq = 20
    
    # Reset sequence numbers using the engine method.
    await fix_engine.reset_sequence_numbers()
    
    # Verify that both inbound and outbound sequence numbers are reset to 1.
    assert fix_engine.message_store.outgoing_seq == 1
    assert fix_engine.message_store.incoming_seq == 1

@pytest.mark.asyncio
async def test_set_sequence_numbers(fix_engine):
    # Set inbound and outbound sequence numbers using engine methods.
    await fix_engine.set_inbound_sequence_number(100)
    await fix_engine.set_outbound_sequence_number(200)
    
    # Check that the dummy message store's sequence numbers reflect the changes.
    assert fix_engine.message_store.incoming_seq == 100
    assert fix_engine.message_store.outgoing_seq == 200
