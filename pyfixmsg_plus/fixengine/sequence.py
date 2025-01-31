import sqlite3

class SequenceManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.sequence_number = self.load_sequence_number()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            DROP TABLE IF EXISTS sessions
        ''')
        cursor.execute('''
            CREATE TABLE sessions (
                beginstring TEXT NOT NULL,
                sendercompid TEXT NOT NULL,
                sendersubid TEXT NOT NULL,
                senderlocid TEXT NOT NULL,
                targetcompid TEXT NOT NULL,
                targetsubid TEXT NOT NULL,
                targetlocid TEXT NOT NULL,
                session_qualifier TEXT NOT NULL,
                creation_time TEXT NOT NULL,
                incoming_seqnum INTEGER NOT NULL,
                outgoing_seqnum INTEGER NOT NULL,
                PRIMARY KEY (beginstring, sendercompid, sendersubid, senderlocid,
                             targetcompid, targetsubid, targetlocid, session_qualifier)
            )
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

# Example usage
if __name__ == "__main__":
    db_path = 'fix_state.db'
    sequence_manager = SequenceManager(db_path)
    print(sequence_manager.get_next_sequence_number())
    print(sequence_manager.get_next_sequence_number())
