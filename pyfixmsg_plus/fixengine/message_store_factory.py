from pyfixmsg_plus.fixengine.database_message_store import DatabaseMessageStore
import os # For example usage cleanup

class MessageStoreFactory:
    @staticmethod
    async def get_message_store(store_type, db_path, beginstring=None, sendercompid=None, targetcompid=None):
        if store_type == 'database':
            store = DatabaseMessageStore(db_path, beginstring, sendercompid, targetcompid)
            await store.initialize()
            return store
        else:
            raise ValueError(f"Unknown store type: {store_type}")
