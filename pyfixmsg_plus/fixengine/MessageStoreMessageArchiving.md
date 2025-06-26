# DatabaseMessageStore Message Archiving and Audit Trail

## Overview

The `DatabaseMessageStore` class provides persistent storage for FIX messages and session state, including sequence numbers.  
To support a **full audit trail**, it archives any message that would be overwritten due to sequence number reuse (such as after a sequence reset or resend).

---

## How It Works

### Main Message Table

- The `messages` table stores the latest message for each `(beginstring, sendercompid, targetcompid, msgseqnum)` combination.
- If a new message arrives with the same keys, it would normally overwrite the old message.

### Archive Table

- The `messages_archive` table stores all previous versions of messages that are about to be overwritten.
- Before overwriting a message in `messages`, the old message is copied to `messages_archive` along with its original timestamp and the time it was archived.

### Archiving Logic

- When `store_message()` is called:
  1. The store checks if a message with the same session and sequence number already exists.
  2. If so, it logs a warning and archives the old message in `messages_archive`.
  3. The new message is then written to the `messages` table.

### Example Scenario

- If you set the incoming or outgoing sequence number to a lower value (to trigger a resend or after a reset), and then store a message with a sequence number that already exists:
  - The previous message is **not lost**—it is moved to the archive table.
  - The latest message is always available in the main `messages` table.

---

## Schema

- **messages**
  - `beginstring`, `sendercompid`, `targetcompid`, `msgseqnum`, `message`, `timestamp`
  - Primary key: `(beginstring, sendercompid, targetcompid, msgseqnum)`

- **messages_archive**
  - `beginstring`, `sendercompid`, `targetcompid`, `msgseqnum`, `message`, `archived_at`, `original_timestamp`
  - Primary key: `(beginstring, sendercompid, targetcompid, msgseqnum, archived_at)`

---

## Benefits

- **Full Audit Trail:** Every version of every message is preserved, even if sequence numbers are reused.
- **Protocol Compliance:** Supports FIX scenarios like resend and sequence resets without data loss.
- **Transparency:** Logs a warning whenever a message is archived due to overwrite.

---

## Usage Notes

- Query the `messages` table for the latest state of the session.
- Query the `messages_archive` table to see all historical messages, including those replaced due to sequence number reuse.
- This design is robust for both production and regulatory/audit requirements.

---

## Example: Querying the Message Store with sqlite3

Below are example `sqlite3` commands to query both the current and archived FIX messages.

---

### 1. Show All Current Messages for a Session

```sql
SELECT * FROM messages
WHERE sendercompid = 'BANZAI' AND targetcompid = 'EXEC'
ORDER BY msgseqnum;
```

---

### 2. Show All Archived Versions for a Specific Sequence Number

```sql
SELECT * FROM messages_archive
WHERE sendercompid = 'BANZAI' AND targetcompid = 'EXEC' AND msgseqnum = 42
ORDER BY archived_at;
```

---

### 3. Show the Full Audit Trail for a Session (All Archived Messages)

```sql
SELECT * FROM messages_archive
WHERE sendercompid = 'BANZAI' AND targetcompid = 'EXEC'
ORDER BY msgseqnum, archived_at;
```

---

### 4. Show the Latest Message for Each Sequence Number (Current State)

```sql
SELECT msgseqnum, message, timestamp
FROM messages
WHERE sendercompid = 'BANZAI' AND targetcompid = 'EXEC'
ORDER BY msgseqnum;
```

---

### 5. Show All Messages (Current + Archived) for a Session

```sql
SELECT msgseqnum, message, timestamp AS event_time, 'current' AS source
FROM messages
WHERE sendercompid = 'BANZAI' AND targetcompid = 'EXEC'
UNION ALL
SELECT msgseqnum, message, archived_at AS event_time, 'archive' AS source
FROM messages_archive
WHERE sendercompid = 'BANZAI' AND targetcompid = 'EXEC'
ORDER BY msgseqnum, event_time;
```

---

**Tip:**  
To run these queries, use the `sqlite3` CLI tool:

```sh
sqlite3 /path/to/your/initiator_fix_state.db
```

Then paste the SQL queries above at the prompt.