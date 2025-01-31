import sqlite3

class SequenceManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.sequence_number = self.load_sequence_number()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sequence (
                id INTEGER PRIMARY KEY, 
                sequence_number INTEGER
            )
        ''')
        cursor.execute('''
            INSERT OR IGNORE INTO sequence (id, sequence_number) 
            VALUES (1, 0)
        ''')
        self.conn.commit()

    def load_sequence_number(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT sequence_number FROM sequence WHERE id = 1
        ''')
        result = cursor.fetchone()
        return result[0] if result else 0

    def save_sequence_number(self, number):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE sequence SET sequence_number = ? WHERE id = 1
        ''', (number,))
        self.conn.commit()

    def get_next_sequence_number(self):
        self.sequence_number += 1
        self.save_sequence_number(self.sequence_number)
        return self.sequence_number
