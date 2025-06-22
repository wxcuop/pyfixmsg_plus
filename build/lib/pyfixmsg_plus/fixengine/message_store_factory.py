from pyfixmsg_plus.fixengine.database_message_store import DatabaseMessageStore
import os # For example usage cleanup

class MessageStoreFactory:
    @staticmethod
    def get_message_store(store_type, db_path, beginstring=None, sendercompid=None, targetcompid=None): # Added optional args
        if store_type == 'database':
            # Pass the identifiers to the DatabaseMessageStore constructor
            return DatabaseMessageStore(db_path, beginstring, sendercompid, targetcompid)
        # elif store_type == 'memory': # Example for a future store type
            # return MemoryMessageStore(beginstring, sendercompid, targetcompid) # Assuming it would take these
        else:
            raise ValueError(f"Unknown store type: {store_type}")

# Example usage (updated to reflect new factory method and DatabaseMessageStore capabilities)
if __name__ == "__main__":
    db_file = 'fix_factory_messages_test.db'
    if os.path.exists(db_file): # Clean up for repeatable test
        os.remove(db_file)

    print("--- Factory Test Case 1: New Session via Factory ---")
    # Pass session identifiers directly through the factory
    store1 = MessageStoreFactory.get_message_store('database', db_file, 
                                                   beginstring='FIX.4.4', 
                                                   sendercompid='FACTORY_SENDER', 
                                                   targetcompid='FACTORY_TARGET')
    
    print(f"Initial: NextIn={store1.get_next_incoming_sequence_number()}, NextOut (peek)={store1.outgoing_seqnum}, IsNew={store1.is_new_session()}")
    
    # Get next outgoing sequence number (this will use and then increment the internal counter)
    seq_to_send = store1.get_next_outgoing_sequence_number() # Expected: 1
    print(f"SeqNum to use for next outgoing message: {seq_to_send}")
    store1.store_message(store1.beginstring, store1.sendercompid, store1.targetcompid, seq_to_send, f"Test message {seq_to_send}")
    print(f"Stored message with SeqNum {seq_to_send}")
    print(f"Retrieved: {store1.get_message(store1.beginstring, store1.sendercompid, store1.targetcompid, seq_to_send)}")

    print(f"After sending 1: NextIn={store1.get_next_incoming_sequence_number()}, NextOut (peek)={store1.outgoing_seqnum}, CurrentOut (last sent)={store1.get_current_outgoing_sequence_number()}")

    # Simulate processing an incoming message
    expected_in = store1.get_next_incoming_sequence_number() # Expected: 1
    print(f"Next expected incoming: {expected_in}")
    # Assume message with expected_in is processed
    store1.increment_incoming_sequence_number()
    print(f"After processing incoming {expected_in}: NextIn={store1.get_next_incoming_sequence_number()}")

    print("\n--- Factory Test Case 2: Reset sequence numbers ---")
    store1.reset_sequence_numbers()
    print(f"After reset: NextIn={store1.get_next_incoming_sequence_number()}, NextOut (peek)={store1.outgoing_seqnum}, IsNew={store1.is_new_session()}")
    print(f"CurrentOut after reset: {store1.get_current_outgoing_sequence_number()}") # Should be 0
    
    store1.close() # Close the store connection

    # Clean up the test database file
    if os.path.exists(db_file):
        os.remove(db_file)
