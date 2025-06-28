from pyfixmsg_plus.fixengine.database_message_store import DatabaseMessageStore
import os
import asyncio

class MessageStoreFactory:
    @staticmethod
    async def get_message_store(store_type, db_path, beginstring=None, sendercompid=None, targetcompid=None):
        if store_type == 'database':
            store = DatabaseMessageStore(db_path, beginstring, sendercompid, targetcompid)
            await store.async_init()
            return store
        # elif store_type == 'memory':
        #     return MemoryMessageStore(beginstring, sendercompid, targetcompid)
        else:
            raise ValueError(f"Unknown store type: {store_type}")

# Example usage (updated for async)
async def main():
    db_file = 'fix_factory_messages_test.db'
    if os.path.exists(db_file):
        os.remove(db_file)

    print("--- Factory Test Case 1: New Session via Factory ---")
    store1 = await MessageStoreFactory.get_message_store(
        'database', db_file,
        beginstring='FIX.4.4',
        sendercompid='FACTORY_SENDER',
        targetcompid='FACTORY_TARGET'
    )

    print(f"Initial: NextIn={store1.get_next_incoming_sequence_number()}, NextOut (peek)={store1.outgoing_seqnum}, IsNew={store1.is_new_session()}")

    # Use the atomic method for outgoing sequence number
    seq_to_send = await store1.get_and_increment_outgoing_sequence_number()
    print(f"SeqNum to use for next outgoing message: {seq_to_send}")
    await store1.store_message(store1.beginstring, store1.sendercompid, store1.targetcompid, seq_to_send, f"Test message {seq_to_send}")
    print(f"Stored message with SeqNum {seq_to_send}")
    msg = await store1.get_message(store1.beginstring, store1.sendercompid, store1.targetcompid, seq_to_send)
    print(f"Retrieved: {msg}")

    print(f"After sending 1: NextIn={store1.get_next_incoming_sequence_number()}, NextOut (peek)={store1.outgoing_seqnum}, CurrentOut (last sent)={store1.get_current_outgoing_sequence_number()}")

    expected_in = store1.get_next_incoming_sequence_number()
    print(f"Next expected incoming: {expected_in}")
    await store1.increment_incoming_sequence_number()
    print(f"After processing incoming {expected_in}: NextIn={store1.get_next_incoming_sequence_number()}")

    print("\n--- Factory Test Case 2: Reset sequence numbers ---")
    await store1.reset_sequence_numbers()
    print(f"After reset: NextIn={store1.get_next_incoming_sequence_number()}, NextOut (peek)={store1.outgoing_seqnum}, IsNew={store1.is_new_session()}")
    print(f"CurrentOut after reset: {store1.get_current_outgoing_sequence_number()}")

    await store1.close()

    if os.path.exists(db_file):
        os.remove(db_file)

if __name__ == "__main__":
    asyncio.run(main())
