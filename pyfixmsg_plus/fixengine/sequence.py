import sqlite3
from datetime import datetime

class SequenceManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.incoming_seqnum, self.outgoing_seqnum = self.load_sequence_numbers()

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

    def load_sequence_numbers(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT incoming_seqnum, outgoing_seqnum FROM sessions WHERE
            beginstring = ? AND sendercompid = ? AND sendersubid = ? AND senderlocid = ? AND
            targetcompid = ? AND targetsubid = ? AND targetlocid = ? AND session_qualifier = ?
        ''', (self.beginstring, self.sendercompid, self.sendersubid, self.senderlocid, 
              self.targetcompid, self.targetsubid, self.targetlocid, self.session_qualifier))
        result = cursor.fetchone()
        if result:
            return result
        else:
            return 0, 0

    def save_sequence_numbers(self, incoming_seqnum, outgoing_seqnum):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO sessions (beginstring, sendercompid, sendersubid, senderlocid, 
                                  targetcompid, targetsubid, targetlocid, session_qualifier, 
                                  creation_time, incoming_seqnum, outgoing_seqnum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(beginstring, sendercompid, sendersubid, senderlocid, targetcompid, 
                        targetsubid, targetlocid, session_qualifier)
            DO UPDATE SET incoming_seqnum = ?, outgoing_seqnum = ?
        ''', (self.beginstring, self.sendercompid, self.sendersubid, self.senderlocid, 
              self.targetcompid, self.targetsubid, self.targetlocid, self.session_qualifier, 
              datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), incoming_seqnum, outgoing_seqnum,
              incoming_seqnum, outgoing_seqnum))
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

    print(sequence_manager.get_next_outgoing_sequence_number())
    print(sequence_manager.get_next_incoming_sequence_number())
    print("Reset sequence numbers to 1")
    sequence_manager.reset_sequence_numbers()
    print(sequence_manager.get_next_outgoing_sequence_number())
    print(sequence_manager.get_next_incoming_sequence_number())
