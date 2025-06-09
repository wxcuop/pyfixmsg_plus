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
        
        # Load sequence numbers on initialization if session identifiers are provided
        if self.beginstring and self.sendercompid and self.targetcompid:
            loaded_in, loaded_out = self.load_sequence_numbers()
            # load_sequence_numbers returns the *next expected/to be used* numbers
            # So, for internal state, we might want to store them as is,
            # or adjust if internal state represents last *processed*.
            # The current get_next_... methods imply internal state is last *processed*.
            # Let's assume load_sequence_numbers gives us the *next expected*.
            # So, last processed incoming is loaded_in - 1, last processed outgoing is loaded_out - 1.
            # However, the current save/load logic seems to store the *next* numbers.
            # Let's stick to the current model: incoming_seqnum and outgoing_seqnum store the *next* number.
            self.incoming_seqnum = loaded_in
            self.outgoing_seqnum = loaded_out
            self.logger.info(f"Loaded sequence numbers for session {self.beginstring}-{self.sendercompid}-{self.targetcompid}: Incoming={self.incoming_seqnum}, Outgoing={self.outgoing_seqnum}")
        else:
            # If session identifiers are not set yet, initialize to 1 (as next expected)
            self.incoming_seqnum = 1
            self.outgoing_seqnum = 1
            self.logger.info("Session identifiers not set at init. Defaulting sequence numbers to 1 (as next expected).")

    def set_session_identifiers(self, beginstring, sendercompid, targetcompid):
        """Allows setting session identifiers after instantiation and attempts to load sequence numbers."""
        if not (self.beginstring and self.sendercompid and self.targetcompid): # Only load if not already set and loaded
            self.beginstring = beginstring
            self.sendercompid = sendercompid
            self.targetcompid = targetcompid
            loaded_in, loaded_out = self.load_sequence_numbers()
            self.incoming_seqnum = loaded_in
            self.outgoing_seqnum = loaded_out
            self.logger.info(f"Session identifiers set. Loaded sequence numbers: Incoming={self.incoming_seqnum}, Outgoing={self.outgoing_seqnum}")
        elif (self.beginstring != beginstring or 
              self.sendercompid != sendercompid or 
              self.targetcompid != targetcompid):
            self.logger.warning("Attempting to change session identifiers on an already initialized store. This is not typical.")
            # Handle as a reset or re-initialization if necessary
            self.beginstring = beginstring
            self.sendercompid = sendercompid
            self.targetcompid = targetcompid
            loaded_in, loaded_out = self.load_sequence_numbers()
            self.incoming_seqnum = loaded_in
            self.outgoing_seqnum = loaded_out


    def create_table(self):
        cursor = self.conn.cursor()
        # Message store: primary key includes direction if storing both incoming and outgoing messages distinctly related to seq num
        # Current key is (beginstring, sendercompid, targetcompid, msgseqnum) - implies msgseqnum is unique for this session tuple.
        # This is fine if get_message is always for *outgoing* messages (as in ResendRequest scenario)
        # or if incoming messages are stored with their original sender/target.
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
        # This stores a message associated with the given compIDs and its original msgseqnum.
        # Used for resending (outgoing) and could be used for auditing incoming.
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO messages (beginstring, sendercompid, targetcompid, msgseqnum, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (beginstring, sendercompid, targetcompid, msgseqnum, message))
            self.conn.commit()
            self.logger.debug(f"Stored message: {sendercompid}->{targetcompid} Seq={msgseqnum}")
        except Exception as e:
            self.logger.error(f"Error storing message for Seq={msgseqnum}: {e}", exc_info=True)


    def get_message(self, beginstring, sendercompid, targetcompid, msgseqnum):
        # Retrieves a message sent *by sendercompid* to *targetcompid* with that msgseqnum.
        # This is used by ResendRequestHandler to get previously *sent* (outgoing) messages.
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
                    self.logger.debug(f"Loaded sequence numbers from DB: Incoming={result[0]}, Outgoing={result[1]}")
                    return int(result[0]), int(result[1]) # Return next expected
            except Exception as e:
                self.logger.error(f"Error loading sequence numbers: {e}", exc_info=True)
        self.logger.debug("No sequence numbers found in DB for session, defaulting to 1,1 (next expected).")
        return 1, 1 # Default for a new session: next expected is 1

    def save_sequence_numbers(self):
        """Saves the current *next expected* sequence numbers for the session."""
        if not (self.beginstring and self.sendercompid and self.targetcompid):
            self.logger.warning("Cannot save sequence numbers: session identifiers not set.")
            return
        try:
            cursor = self.conn.cursor()
            # Storing the *next* sequence numbers
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


    def get_next_incoming_sequence_number(self):
        """Returns the *next expected* incoming sequence number. Does not auto-increment here."""
        # The increment should happen *after* a message with this sequence number is successfully processed.
        return self.incoming_seqnum

    def get_next_outgoing_sequence_number(self):
        """Returns the *next* outgoing sequence number to be used and increments the internal counter."""
        current_seqnum_to_use = self.outgoing_seqnum
        self.outgoing_seqnum += 1
        self.save_sequence_numbers() # Save after determining the next one
        return current_seqnum_to_use


    def set_incoming_sequence_number(self, number):
        """Sets the *next expected* incoming sequence number."""
        if not isinstance(number, int) or number < 1:
            self.logger.error(f"Invalid attempt to set incoming sequence number to: {number}")
            return
        self.incoming_seqnum = number
        self.save_sequence_numbers()
        self.logger.info(f"Next incoming sequence number set to: {self.incoming_seqnum}")


    def set_outgoing_sequence_number(self, number):
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

    # --- New methods required by handlers ---

    def is_new_session(self) -> bool:
        """
        Checks if the current session state (based on loaded/set sequence numbers)
        indicates a new session (i.e., next expected for both incoming and outgoing is 1).
        """
        # load_sequence_numbers already defaults to 1,1 if no session found.
        # So, self.incoming_seqnum and self.outgoing_seqnum would be 1.
        is_new = (self.incoming_seqnum == 1 and self.outgoing_seqnum == 1)
        self.logger.debug(f"is_new_session check: IncomingNext={self.incoming_seqnum}, OutgoingNext={self.outgoing_seqnum}. Is new? {is_new}")
        return is_new

    def get_current_outgoing_sequence_number(self) -> int:
        """
        Returns the sequence number of the *last successfully sent and stored* outgoing message.
        This is `self.outgoing_seqnum - 1` because self.outgoing_seqnum stores the *next* one to be used.
        Returns 0 if no messages have been sent yet in the current session context.
        """
        if self.outgoing_seqnum > 1:
            # self.outgoing_seqnum is the *next* number to be used.
            # So, the one before it was the last one *actually* used.
            last_used = self.outgoing_seqnum - 1
            self.logger.debug(f"get_current_outgoing_sequence_number: NextOutgoing is {self.outgoing_seqnum}, so current (last used) is {last_used}")
            return last_used
        else:
            # If self.outgoing_seqnum is 1, it means no message has been assigned seq num 1 yet.
            self.logger.debug("get_current_outgoing_sequence_number: NextOutgoing is 1, so no messages sent yet in this context. Returning 0.")
            return 0
            
    def increment_incoming_sequence_number(self):
        """Increments the next expected incoming sequence number. Call after processing a message."""
        self.incoming_seqnum +=1
        self.save_sequence_numbers()
        self.logger.debug(f"Incremented incoming sequence. Next expected is now: {self.incoming_seqnum}")


    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.logger.info("Database connection closed.")

# Example usage (updated)
if __name__ == "__main__":
    import os
    db_file = 'fix_messages_test.db'
    if os.path.exists(db_file):
        os.remove(db_file)

    print("--- Test Case 1: New Session ---")
    store1 = DatabaseMessageStore(db_file, 'FIX.4.4', 'SENDER1', 'TARGET1')
    print(f"Initial: NextIn={store1.incoming_seqnum}, NextOut={store1.outgoing_seqnum}, IsNew={store1.is_new_session()}")
    print(f"GetNextOut: {store1.get_next_outgoing_sequence_number()}") # Should be 1, internal next becomes 2
    store1.store_message('FIX.4.4', 'SENDER1', 'TARGET1', 1, "Message 1 from SENDER1")
    print(f"After send 1: NextIn={store1.incoming_seqnum}, NextOut={store1.outgoing_seqnum}, CurrentOut={store1.get_current_outgoing_sequence_number()}")
    print(f"GetNextIn (doesn't increment): {store1.get_next_incoming_sequence_number()}") # Should be 1
    store1.increment_incoming_sequence_number() # Simulate processing incoming message 1
    print(f"After receive 1: NextIn={store1.incoming_seqnum}, NextOut={store1.outgoing_seqnum}")
    store1.close()

    print("\n--- Test Case 2: Load Existing Session ---")
    store2 = DatabaseMessageStore(db_file, 'FIX.4.4', 'SENDER1', 'TARGET1')
    print(f"Loaded: NextIn={store2.incoming_seqnum}, NextOut={store2.outgoing_seqnum}, IsNew={store2.is_new_session()}")
    print(f"GetNextOut: {store2.get_next_outgoing_sequence_number()}") # Should be 2
    store2.store_message('FIX.4.4', 'SENDER1', 'TARGET1', 2, "Message 2 from SENDER1")
    print(f"After send 2: CurrentOut={store2.get_current_outgoing_sequence_number()}") # Should be 2
    store2.close()

    print("\n--- Test Case 3: Reset ---")
    store3 = DatabaseMessageStore(db_file, 'FIX.4.4', 'SENDER1', 'TARGET1')
    print(f"Before Reset: NextIn={store3.incoming_seqnum}, NextOut={store3.outgoing_seqnum}")
    store3.reset_sequence_numbers()
    print(f"After Reset: NextIn={store3.incoming_seqnum}, NextOut={store3.outgoing_seqnum}, IsNew={store3.is_new_session()}")
    print(f"CurrentOut after reset: {store3.get_current_outgoing_sequence_number()}") # Should be 0
    store3.close()

    print("\n--- Test Case 4: Set Identifiers Later ---")
    if os.path.exists(db_file): os.remove(db_file) # Clean slate
    store4_no_id = DatabaseMessageStore(db_file)
    print(f"No ID: NextIn={store4_no_id.incoming_seqnum}, NextOut={store4_no_id.outgoing_seqnum}")
    store4_no_id.set_session_identifiers('FIX.4.2', 'SENDERX', 'TARGETX')
    print(f"ID Set: NextIn={store4_no_id.incoming_seqnum}, NextOut={store4_no_id.outgoing_seqnum}, IsNew={store4_no_id.is_new_session()}")
    first_out = store4_no_id.get_next_outgoing_sequence_number()
    store4_no_id.store_message('FIX.4.2', 'SENDERX', 'TARGETX', first_out, "Test")
    print(f"CurrentOut: {store4_no_id.get_current_outgoing_sequence_number()}")
    store4_no_id.close()
