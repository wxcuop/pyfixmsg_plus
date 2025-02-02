import sqlite3
from datetime import datetime

class DatabaseMessageStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.beginstring = None
        self.sendercompid = None
        self.targetcompid = None
        self.incoming_seqnum, self.outgoing_seqnum = 0, 0

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                beginstring TEXT NOT NULL,
                sendercompid TEXT NOT NULL,
                targetcompid TEXT NOT NULL,
                msgseqnum INTEGER NOT NULL,
                message TEXT NOT NULL,
                PRIMARY KEY (beginstring, sendercompid, targetcompid, msgseqnum)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                beginstring TEXT NOT NULL,
                sendercompid TEXT NOT NULL,
                targetcompid TEXT NOT NULL,
                creation_time TEXT NOT NULL,
                incoming_seqnum INTEGER NOT NULL,
                outgoing_seqnum INTEGER NOT NULL,
                PRIMARY KEY (beginstring, sendercompid, targetcompid)
            )
        ''')
        self.conn.commit()

    def store_message(self, beginstring, sendercompid, targetcompid, msgseqnum, message):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO messages (beginstring, sendercompid, targetcompid, msgseqnum, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (beginstring, sendercompid, targetcompid, msgseqnum, message))
        self.conn.commit()

    def get_message(self, beginstring, sendercompid, targetcompid, msgseqnum):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT message FROM messages WHERE beginstring = ? AND sendercompid = ? AND targetcompid = ? AND msgseqnum = ?
        ''', (beginstring, sendercompid, targetcompid, msgseqnum))
        result = cursor.fetchone()
        return result[0] if result else None

    def load_sequence_numbers(self):
        if self.beginstring and self.sendercompid and self.targetcompid:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT incoming_seqnum, outgoing_seqnum FROM sessions WHERE
                beginstring = ? AND sendercompid = ? AND targetcompid = ?
            ''', (self.beginstring, self.sendercompid, self.targetcompid))
            result = cursor.fetchone()
            if result:
                return result
        return 0, 0

    def save_sequence_numbers(self, incoming_seqnum, outgoing_seqnum):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (beginstring, sendercompid, targetcompid, creation_time, incoming_seqnum, outgoing_seqnum)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(beginstring, sendercompid, targetcompid)
            DO UPDATE SET incoming_seqnum = ?, outgoing_seqnum = ?
        ''', (self.beginstring, self.sendercompid, self.targetcompid, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
              incoming_seqnum, outgoing_seqnum, incoming_seqnum, outgoing_seqnum))
        self.conn.commit()

    def get_next_incoming_sequence_number(self):
        self.incoming_seqnum += 1
        self.save_sequence_numbers(self.incoming_seqnum, self.outgoing_seqnum)
        return self.incoming_seqnum

    def get_next_outgoing_sequence_number(self):
        self.outgoing_seqnum += 1
        self.save_sequence_numbers(self.incoming_seqnum, self.outgoing_seqnum)
        return self.outgoing_seqnum

    def set_incoming_sequence_number(self, number):
        self.incoming_seqnum = number
        self.save_sequence_numbers(self.incoming_seqnum, self.outgoing_seqnum)

    def set_outgoing_sequence_number(self, number):
        self.outgoing_seqnum = number
        self.save_sequence_numbers(self.incoming_seqnum, self.outgoing_seqnum)

    def reset_sequence_numbers(self):
        self.incoming_seqnum = 1
        self.outgoing_seqnum = 1
        self.save_sequence_numbers(self.incoming_seqnum, self.outgoing_seqnum)

# Example usage
if __name__ == "__main__":
    db_path = 'fix_messages.db'
    store = DatabaseMessageStore(db_path)
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
