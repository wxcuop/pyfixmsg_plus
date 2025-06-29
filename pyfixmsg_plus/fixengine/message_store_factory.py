from pyfixmsg_plus.fixengine.database_message_store import DatabaseMessageStore
from typing import Optional, Any

class MessageStoreFactory:
    @staticmethod
    async def get_message_store(
        store_type: str,
        db_path: str,
        beginstring: Optional[str] = None,
        sendercompid: Optional[str] = None,
        targetcompid: Optional[str] = None
    ) -> Any:
        if store_type == 'database':
            store = DatabaseMessageStore(db_path, beginstring, sendercompid, targetcompid)
            await store.initialize()
            return store
        else:
            raise ValueError(f"Unknown store type: {store_type}")
