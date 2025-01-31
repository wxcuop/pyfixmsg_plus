from pyfixmsg_plus.fixengine.database_message_store import DatabaseMessageStore

class MessageStoreFactory:
    @staticmethod
    def get_message_store(store_type, db_path):
        if store_type == 'database':
            return DatabaseMessageStore(db_path)
        else:
            raise ValueError(f"Unknown store type: {store_type}")

# Example usage
if __name__ == "__main__":
    db_path = 'fix_messages.db'
    store = MessageStoreFactory.get_message_store('database', db_path)
    store.beginstring = 'FIX.4.4'
    store.sendercompid = 'SENDER'
    store.targetcompid = 'TARGET'
    
    store.store_message('FIX.4.4', 'SENDER', 'TARGET', 1, 'Test message')
    print(store.get_message('FIX.4.4', 'SENDER', 'TARGET', 1))

    print(store.get_next_outgoing_sequence_number())
    print(store.get_next_incoming_sequence_number())
    print("Reset sequence numbers to 1")
    store.reset_sequence_numbers()
    print(store.get_next_outgoing_sequence_number())
    print(store.get_next_incoming_sequence_number())
