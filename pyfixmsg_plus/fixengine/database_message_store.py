import sqlite3

class DatabaseMessageStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                seq_num INTEGER,
                direction TEXT,
                message TEXT,
                PRIMARY KEY (seq_num, direction)
            )
        ''')
        self.conn.commit()

    def store_message(self, seq_num, direction, message):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO messages (seq_num, direction, message)
            VALUES (?, ?, ?)
        ''', (seq_num, direction, message))
        self.conn.commit()

    def get_message(self, seq_num, direction):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT message FROM messages WHERE seq_num = ? AND direction = ?
        ''', (seq_num, direction))
        result = cursor.fetchone()
        return result[0] if result else None
