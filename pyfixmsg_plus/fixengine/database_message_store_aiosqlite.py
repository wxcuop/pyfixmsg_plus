import aiosqlite
from datetime import datetime, UTC
import logging
import asyncio
import os

class DatabaseMessageStoreAioSqlite:
    """
    An asynchronous message store implementation using aiosqlite.
    """
    def __init__(self, db_path, beginstring=None, sendercompid=None, targetcompid=None):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.conn = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._lock = asyncio.Lock()
        self.beginstring = beginstring
        self.sendercompid = sendercompid
        self.targetcompid = targetcompid
        self.incoming_seqnum = 1
        self.outgoing_seqnum = 1

    async def initialize(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.create_table()
        if self.beginstring and self.sendercompid and self.targetcompid:
            loaded_in, loaded_out = await self.load_sequence_numbers()
            self.incoming_seqnum = loaded_in
            self.outgoing_seqnum = loaded_out
            self.logger.info(f"Loaded sequence numbers for session {self.beginstring}-{self.sendercompid}-{self.targetcompid}: NextIncoming={self.incoming_seqnum}, NextOutgoing={self.outgoing_seqnum}")
        else:
            self.logger.info("Session identifiers not set at init. Defaulting sequence numbers to 1.")

    async def create_table(self):
        async with self.conn.cursor() as cursor:
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    beginstring TEXT, sendercompid TEXT, targetcompid TEXT, 
                    msgseqnum INTEGER, message TEXT, timestamp DATETIME,
                    PRIMARY KEY (beginstring, sendercompid, targetcompid, msgseqnum)
                )
            ''')
            await cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    beginstring TEXT, sendercompid TEXT, targetcompid TEXT,
                    creation_time TEXT, next_incoming_seqnum INTEGER, next_outgoing_seqnum INTEGER,
                    PRIMARY KEY (beginstring, sendercompid, targetcompid)
                )
            ''')
        await self.conn.commit()

    async def store_message(self, beginstring, sendercompid, targetcompid, msgseqnum, message):
        async with self._lock:
            async with self.conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT OR REPLACE INTO messages (beginstring, sendercompid, targetcompid, msgseqnum, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (beginstring, sendercompid, targetcompid, msgseqnum, message, datetime.now(UTC))
                )
            await self.conn.commit()

    async def get_message(self, beginstring, sendercompid, targetcompid, msgseqnum):
        async with self._lock:
            async with self.conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT message FROM messages WHERE beginstring = ? AND sendercompid = ? AND targetcompid = ? AND msgseqnum = ?",
                    (beginstring, sendercompid, targetcompid, msgseqnum)
                )
                row = await cursor.fetchone()
                return row[0] if row else None

    async def load_sequence_numbers(self):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT next_incoming_seqnum, next_outgoing_seqnum FROM sessions WHERE beginstring = ? AND sendercompid = ? AND targetcompid = ?",
                (self.beginstring, self.sendercompid, self.targetcompid)
            )
            row = await cursor.fetchone()
            return (int(row[0]), int(row[1])) if row else (1, 1)

    async def save_sequence_numbers(self):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO sessions (beginstring, sendercompid, targetcompid, creation_time, next_incoming_seqnum, next_outgoing_seqnum)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(beginstring, sendercompid, targetcompid) DO UPDATE SET
                    next_incoming_seqnum=excluded.next_incoming_seqnum,
                    next_outgoing_seqnum=excluded.next_outgoing_seqnum
                """,
                (self.beginstring, self.sendercompid, self.targetcompid, datetime.now(UTC), self.incoming_seqnum, self.outgoing_seqnum)
            )
        await self.conn.commit()

    def get_next_incoming_sequence_number(self) -> int:
        return self.incoming_seqnum

    async def increment_incoming_sequence_number(self):
        async with self._lock:
            self.incoming_seqnum += 1
            await self.save_sequence_numbers()

    def get_next_outgoing_sequence_number(self) -> int:
        return self.outgoing_seqnum

    async def increment_outgoing_sequence_number(self):
        async with self._lock:
            self.outgoing_seqnum += 1
            await self.save_sequence_numbers()

    async def set_incoming_sequence_number(self, number: int):
        async with self._lock:
            self.incoming_seqnum = number
            await self.save_sequence_numbers()

    async def set_outgoing_sequence_number(self, number: int):
        async with self._lock:
            self.outgoing_seqnum = number
            await self.save_sequence_numbers()

    async def reset_sequence_numbers(self):
        async with self._lock:
            self.incoming_seqnum = 1
            self.outgoing_seqnum = 1
            await self.save_sequence_numbers()

    def get_current_outgoing_sequence_number(self) -> int:
        return self.outgoing_seqnum - 1 if self.outgoing_seqnum > 1 else 0

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.logger.info("Database connection closed.")