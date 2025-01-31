import sqlite3
from datetime import datetime

class SequenceManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.sequence_number = self.load_sequence_number()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
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
            SELECT outgoing_seqnum FROM sessions WHERE
            beginstring = ? AND sendercompid = ? AND sendersubid = ? AND senderlocid = ? AND
            targetcompid = ? AND targetsubid = ? AND targetlocid = ? AND session_qualifier = ?
        ''', (self.beginstring, self.sendercompid, self.sendersubid, self.senderlocid, 
              self.targetcompid, self.targetsubid, self.targetlocid, self.session_qualifier))
        result = cursor.fetchone()
        return result[0] if result else 0

    def save_sequence_number(self, number):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (beginstring, sendercompid, sendersubid, senderlocid, 
                                  targetcompid, targetsubid, targetlocid, session_qualifier, 
                                  creation_time, incoming_seqnum, outgoing_seqnum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(beginstring, sendercompid, sendersubid, senderlocid, targetcompid, 
                        targetsubid, targetlocid, session_qualifier)
            DO UPDATE SET outgoing_seqnum = ?
        ''', (self.beginstring, self.sendercompid, self.sendersubid, self.senderlocid, 
              self.targetcompid, self.targetsubid, self.targetlocid, self.session_qualifier, 
              datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), 0, number, number))
        self.conn.commit()

    def get_next_sequence_number(self):
        self.sequence_number += 1
        self.save_sequence_number(self.sequence_number)
        return self.sequence_number

# Example usage
if __name__ == "__main__":
    db_path = 'fix_state.db'
    sequence_manager = SequenceManager(db_path)
    sequence_manager.beginstring = 'FIX.4.4'
    sequence_manager.sendercompid = 'SENDER'
    sequence_manager.sendersubid = ''
    sequence_manager.senderlocid = ''
    sequence_manager.targetcompid = 'TARGET'
    sequence_manager.targetsubid = ''
    sequence_manager.targetlocid = ''
    sequence_manager.session_qualifier = ''
    print(sequence_manager.get_next_sequence_number())
    print(sequence_manager.get_next_sequence_number())
