import sqlite3

class DatabaseMessageStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()

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

# Example usage
if __name__ == "__main__":
    db_path = 'fix_messages.db'
    store = DatabaseMessageStore(db_path)
    store.store_message('FIX.4.4', 'SENDER', 'TARGET', 1, 'Test message')
    print(store.get_message('FIX.4.4', 'SENDER', 'TARGET', 1))
