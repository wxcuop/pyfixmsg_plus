import sqlite3
from datetime import datetime, UTC
import logging # Added logging

class DatabaseMessageStore:
    def __init__(self, db_path, beginstring=None, sendercompid=None, targetcompid=None): # Added session identifiers
        self.db_path = db_path # Store db_path for potential re-connect if needed
        self.conn = sqlite3.connect(db_path)
        self.logger = logging.getLogger(self.__class__.__name__) # Added logger
        self.create_table()
        
        self.beginstring = beginstring
        self.sendercompid = sendercompid
        self.targetcompid = targetcompid
        
        if self.beginstring and self.sendercompid and self.targetcompid:
            loaded_in, loaded_out = self.load_sequence_numbers()
            self.incoming_seqnum = loaded_in # Stores the next expected incoming sequence number
            self.outgoing_seqnum = loaded_out # Stores the next outgoing sequence number to be used
            self.logger.info(f"Loaded sequence numbers for session {self.beginstring}-{self.sendercompid}-{self.targetcompid}: NextIncoming={self.incoming_seqnum}, NextOutgoing={self.outgoing_seqnum}")
        else:
            self.incoming_seqnum = 1
            self.outgoing_seqnum = 1
            self.logger.info("Session identifiers not set at init. Defaulting sequence numbers to 1 (as next expected).")

    def set_session_identifiers(self, beginstring, sendercompid, targetcompid):
        """Allows setting session identifiers after instantiation and attempts to load sequence numbers."""
        should_load = False
        if not (self.beginstring and self.sendercompid and self.targetcompid):
            should_load = True
        elif (self.beginstring != beginstring or 
              self.sendercompid != sendercompid or 
              self.targetcompid != targetcompid):
            self.logger.warning("Attempting to change session identifiers on an already initialized store. This is not typical. Reloading sequences.")
            should_load = True

        if should_load:
            self.beginstring = beginstring
            self.sendercompid = sendercompid
            self.targetcompid = targetcompid
            loaded_in, loaded_out = self.load_sequence_numbers()
            self.incoming_seqnum = loaded_in
            self.outgoing_seqnum = loaded_out
            self.logger.info(f"Session identifiers set/updated. Loaded sequence numbers: NextIncoming={self.incoming_seqnum}, NextOutgoing={self.outgoing_seqnum}")


    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                beginstring TEXT NOT NULL,
                sendercompid TEXT NOT NULL, 
                targetcompid TEXT NOT NULL, 
                msgseqnum INTEGER NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (beginstring, sendercompid, targetcompid, msgseqnum) 
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages_archive (
                beginstring TEXT NOT NULL,
                sendercompid TEXT NOT NULL, 
                targetcompid TEXT NOT NULL, 
                msgseqnum INTEGER NOT NULL,
                message TEXT NOT NULL,
                archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                original_timestamp DATETIME,
                PRIMARY KEY (beginstring, sendercompid, targetcompid, msgseqnum, archived_at)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                beginstring TEXT NOT NULL,
                sendercompid TEXT NOT NULL,
                targetcompid TEXT NOT NULL,
                creation_time TEXT NOT NULL,
                next_incoming_seqnum INTEGER NOT NULL, 
                next_outgoing_seqnum INTEGER NOT NULL, 
                PRIMARY KEY (beginstring, sendercompid, targetcompid)
            )
        ''')
        self.conn.commit()

    def store_message(self, beginstring, sendercompid, targetcompid, msgseqnum, message):
        try:
            cursor = self.conn.cursor()
            # Check if a message with this seqnum already exists (i.e., possible overwrite)
            cursor.execute('''
                SELECT message, timestamp FROM messages WHERE beginstring = ? AND sendercompid = ? AND targetcompid = ? AND msgseqnum = ?
            ''', (beginstring, sendercompid, targetcompid, msgseqnum))
            existing = cursor.fetchone()
            if existing:
                self.logger.warning(
                    f"Archiving and overwriting existing message for {sendercompid}->{targetcompid} Seq={msgseqnum} in DB. "
                    "This usually happens when sequence numbers are reused (e.g., after a reset or resend)."
                )
                # Archive the old message
                cursor.execute('''
                    INSERT INTO messages_archive (beginstring, sendercompid, targetcompid, msgseqnum, message, original_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (beginstring, sendercompid, targetcompid, msgseqnum, existing[0], existing[1]))
            cursor.execute('''
                INSERT OR REPLACE INTO messages (beginstring, sendercompid, targetcompid, msgseqnum, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (beginstring, sendercompid, targetcompid, msgseqnum, message))
            self.conn.commit()
            self.logger.debug(f"Stored message: {sendercompid}->{targetcompid} Seq={msgseqnum}")
        except Exception as e:
            self.logger.error(f"Error storing message for Seq={msgseqnum}: {e}", exc_info=True)


    def get_message(self, beginstring, sendercompid, targetcompid, msgseqnum):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT message FROM messages WHERE beginstring = ? AND sendercompid = ? AND targetcompid = ? AND msgseqnum = ?
            ''', (beginstring, sendercompid, targetcompid, msgseqnum))
            result = cursor.fetchone()
            if result:
                self.logger.debug(f"Retrieved message for {sendercompid}->{targetcompid} Seq={msgseqnum}")
                return result[0]
            else:
                self.logger.debug(f"No message found for {sendercompid}->{targetcompid} Seq={msgseqnum}")
                return None
        except Exception as e:
            self.logger.error(f"Error retrieving message for Seq={msgseqnum}: {e}", exc_info=True)
            return None


    def load_sequence_numbers(self):
        """Loads the *next expected* sequence numbers for the current session."""
        if self.beginstring and self.sendercompid and self.targetcompid:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT next_incoming_seqnum, next_outgoing_seqnum FROM sessions WHERE
                    beginstring = ? AND sendercompid = ? AND targetcompid = ?
                ''', (self.beginstring, self.sendercompid, self.targetcompid))
                result = cursor.fetchone()
                if result:
                    self.logger.debug(f"Loaded sequence numbers from DB: NextIncoming={result[0]}, NextOutgoing={result[1]}")
                    return int(result[0]), int(result[1]) 
            except Exception as e:
                self.logger.error(f"Error loading sequence numbers: {e}", exc_info=True)
        self.logger.debug("No sequence numbers found in DB for session, defaulting to 1,1 (next expected).")
        return 1, 1 

    def save_sequence_numbers(self):
        """Saves the current *next expected* sequence numbers for the session."""
        if not (self.beginstring and self.sendercompid and self.targetcompid):
            self.logger.warning("Cannot save sequence numbers: session identifiers not set.")
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (beginstring, sendercompid, targetcompid, creation_time, next_incoming_seqnum, next_outgoing_seqnum)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(beginstring, sendercompid, targetcompid)
                DO UPDATE SET next_incoming_seqnum = excluded.next_incoming_seqnum, 
                              next_outgoing_seqnum = excluded.next_outgoing_seqnum,
                              creation_time = CASE WHEN excluded.next_incoming_seqnum = 1 AND excluded.next_outgoing_seqnum = 1 
                                                   THEN excluded.creation_time 
                                                   ELSE creation_time END
            ''', (self.beginstring, self.sendercompid, self.targetcompid, 
                  datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                  self.incoming_seqnum, self.outgoing_seqnum))
            self.conn.commit()
            self.logger.debug(f"Saved sequence numbers: Next Incoming={self.incoming_seqnum}, Next Outgoing={self.outgoing_seqnum}")
        except Exception as e:
            self.logger.error(f"Error saving sequence numbers: {e}", exc_info=True)


    def get_next_incoming_sequence_number(self) -> int:
        """Returns the *next expected* incoming sequence number."""
        return self.incoming_seqnum

    def increment_incoming_sequence_number(self):
        """Increments the next expected incoming sequence number. Call after processing a message."""
        self.incoming_seqnum +=1
        self.save_sequence_numbers()
        self.logger.debug(f"Incremented incoming sequence. Next expected is now: {self.incoming_seqnum}")

    def get_next_outgoing_sequence_number(self) -> int:
        """Returns the *next* outgoing sequence number to be used. Does NOT auto-increment."""
        return self.outgoing_seqnum

    def increment_outgoing_sequence_number(self):
        """Increments the next outgoing sequence number. Call after using the current number."""
        self.outgoing_seqnum += 1
        self.save_sequence_numbers()
        self.logger.debug(f"Incremented outgoing sequence. Next to be used is now: {self.outgoing_seqnum}")


    def set_incoming_sequence_number(self, number: int):
        """Sets the *next expected* incoming sequence number."""
        if not isinstance(number, int) or number < 1:
            self.logger.error(f"Invalid attempt to set incoming sequence number to: {number}")
            return
        self.incoming_seqnum = number
        self.save_sequence_numbers()
        self.logger.info(f"Next incoming sequence number set to: {self.incoming_seqnum}")


    def set_outgoing_sequence_number(self, number: int):
        """Sets the *next* outgoing sequence number to be used."""
        if not isinstance(number, int) or number < 1:
            self.logger.error(f"Invalid attempt to set outgoing sequence number to: {number}")
            return
        self.outgoing_seqnum = number
        self.save_sequence_numbers()
        self.logger.info(f"Next outgoing sequence number set to: {self.outgoing_seqnum}")


    def reset_sequence_numbers(self):
        """Resets both *next expected* sequence numbers to 1."""
        self.logger.info(f"Resetting sequence numbers for session {self.beginstring}-{self.sendercompid}-{self.targetcompid} to 1.")
        self.incoming_seqnum = 1
        self.outgoing_seqnum = 1
        self.save_sequence_numbers()

    def is_new_session(self) -> bool:
        """
        Checks if the current session state (based on loaded/set sequence numbers)
        indicates a new session (i.e., next expected for both incoming and outgoing is 1).
        """
        is_new = (self.incoming_seqnum == 1 and self.outgoing_seqnum == 1)
        self.logger.debug(f"is_new_session check: NextIncoming={self.incoming_seqnum}, NextOutgoing={self.outgoing_seqnum}. Is new? {is_new}")
        return is_new

    def get_current_outgoing_sequence_number(self) -> int:
        """
        Returns the sequence number of the *last successfully sent and stored* outgoing message.
        This is `self.outgoing_seqnum - 1` because self.outgoing_seqnum stores the *next* one to be used.
        Returns 0 if no messages have been sent yet in the current session context.
        """
        if self.outgoing_seqnum > 1:
            last_used = self.outgoing_seqnum - 1
            self.logger.debug(f"get_current_outgoing_sequence_number: NextOutgoing is {self.outgoing_seqnum}, so current (last used) is {last_used}")
            return last_used
        else:
            self.logger.debug("get_current_outgoing_sequence_number: NextOutgoing is 1, so no messages sent yet in this context. Returning 0.")
            return 0
            
    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed.")

# Example usage (updated to reflect new get_next/increment pattern)
if __name__ == "__main__":
    import os
    db_file = 'fix_messages_test.db'
    if os.path.exists(db_file):
        os.remove(db_file)
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("\n--- Test Case 1: New Session ---")
    store1 = DatabaseMessageStore(db_file, 'FIX.4.4', 'SENDER1', 'TARGET1')
    print(f"Initial: NextIn={store1.get_next_incoming_sequence_number()}, NextOut={store1.get_next_outgoing_sequence_number()}, IsNew={store1.is_new_session()}")
    
    seq_to_send1 = store1.get_next_outgoing_sequence_number() # Should be 1
    print(f"Seq to send1: {seq_to_send1}")
    store1.store_message('FIX.4.4', 'SENDER1', 'TARGET1', seq_to_send1, f"Message {seq_to_send1} from SENDER1")
    store1.increment_outgoing_sequence_number() # Increment after using 1, internal next becomes 2
    print(f"After send 1: NextIn={store1.get_next_incoming_sequence_number()}, NextOut={store1.get_next_outgoing_sequence_number()}, CurrentOut={store1.get_current_outgoing_sequence_number()}")
    
    print(f"GetNextIn (doesn't increment): {store1.get_next_incoming_sequence_number()}") # Should be 1
    store1.increment_incoming_sequence_number() # Simulate processing incoming message 1, internal next becomes 2
    print(f"After receive 1: NextIn={store1.get_next_incoming_sequence_number()}, NextOut={store1.get_next_outgoing_sequence_number()}")
    store1.close()

    print("\n--- Test Case 2: Load Existing Session ---")
    store2 = DatabaseMessageStore(db_file, 'FIX.4.4', 'SENDER1', 'TARGET1')
    print(f"Loaded: NextIn={store2.get_next_incoming_sequence_number()}, NextOut={store2.get_next_outgoing_sequence_number()}, IsNew={store2.is_new_session()}")
    
    seq_to_send2 = store2.get_next_outgoing_sequence_number() # Should be 2
    print(f"Seq to send2: {seq_to_send2}")
    store2.store_message('FIX.4.4', 'SENDER1', 'TARGET1', seq_to_send2, f"Message {seq_to_send2} from SENDER1")
    store2.increment_outgoing_sequence_number() # Increment after using 2, internal next becomes 3
    print(f"After send 2: NextOut={store2.get_next_outgoing_sequence_number()}, CurrentOut={store2.get_current_outgoing_sequence_number()}") # Should be 3, 2
    store2.close()

    print("\n--- Test Case 3: Reset ---")
    store3 = DatabaseMessageStore(db_file, 'FIX.4.4', 'SENDER1', 'TARGET1')
    print(f"Before Reset: NextIn={store3.get_next_incoming_sequence_number()}, NextOut={store3.get_next_outgoing_sequence_number()}")
    store3.reset_sequence_numbers()
    print(f"After Reset: NextIn={store3.get_next_incoming_sequence_number()}, NextOut={store3.get_next_outgoing_sequence_number()}, IsNew={store3.is_new_session()}")
    print(f"CurrentOut after reset: {store3.get_current_outgoing_sequence_number()}") # Should be 0
    store3.close()

    print("\n--- Test Case 4: Set Identifiers Later ---")
    if os.path.exists(db_file): os.remove(db_file) # Clean slate
    store4_no_id = DatabaseMessageStore(db_file)
    print(f"No ID: NextIn={store4_no_id.get_next_incoming_sequence_number()}, NextOut={store4_no_id.get_next_outgoing_sequence_number()}")
    store4_no_id.set_session_identifiers('FIX.4.2', 'SENDERX', 'TARGETX')
    print(f"ID Set: NextIn={store4_no_id.get_next_incoming_sequence_number()}, NextOut={store4_no_id.get_next_outgoing_sequence_number()}, IsNew={store4_no_id.is_new_session()}")
    
    first_out_s4 = store4_no_id.get_next_outgoing_sequence_number()
    store4_no_id.store_message('FIX.4.2', 'SENDERX', 'TARGETX', first_out_s4, "Test S4")
    store4_no_id.increment_outgoing_sequence_number()
    print(f"CurrentOut S4: {store4_no_id.get_current_outgoing_sequence_number()}")
    store4_no_id.close()
