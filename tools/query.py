import argparse
import asyncio
import sys
from pyfixmsg_plus.fixengine.engine import FixEngine
from pyfixmsg_plus.fixengine.configmanager import ConfigManager

def print_message(msg):
    if msg is None:
        print("No message found.")
    else:
        for tag, value in msg.items():
            print(f"{tag}: {value}")

async def main():
    parser = argparse.ArgumentParser(
        description="Query FIX messages via the engine's API."
    )
    parser.add_argument(
        "--config", required=True, help="Path to the FIX engine config file (e.g., config_initiator.ini)"
    )
    parser.add_argument(
        "--session", required=True, help="Session ID in the form SENDER-TARGET (e.g., BANZAI-EXEC)"
    )
    parser.add_argument(
        "--seqnum", type=int, help="Sequence number to query (if omitted, shows all for session)"
    )
    parser.add_argument(
        "--clordid", help="Query by ClOrdID (tag 11) value"
    )
    parser.add_argument(
        "--archive", action="store_true", help="Query archived (overwritten) messages instead of current"
    )

    args = parser.parse_args()

    sender, target = args.session.split("-", 1)
    config = ConfigManager(args.config)
    engine = FixEngine(config, application=None)  # No app needed for query

    store = engine.message_store

    if args.clordid:
        # Query by ClOrdID (tag 11)
        if args.archive:
            cursor = store.conn.cursor()
            cursor.execute(
                "SELECT msgseqnum, message, archived_at FROM messages_archive WHERE sendercompid=? AND targetcompid=? ORDER BY msgseqnum, archived_at",
                (sender, target),
            )
            rows = cursor.fetchall()
        else:
            cursor = store.conn.cursor()
            cursor.execute(
                "SELECT msgseqnum, message, timestamp FROM messages WHERE sendercompid=? AND targetcompid=? ORDER BY msgseqnum",
                (sender, target),
            )
            rows = cursor.fetchall()
        found = False
        for row in rows:
            msgseqnum, message, ts = row
            # Parse message to find tag 11
            from pyfixmsg.fixmessage import FixMessage
            fixmsg = FixMessage()
            try:
                fixmsg.load_fix(message)
            except Exception:
                continue
            if 11 in fixmsg and str(fixmsg[11]) == args.clordid:
                print(f"SeqNum: {msgseqnum}, Timestamp: {ts}")
                print(message)
                print("-" * 40)
                found = True
        if not found:
            print(f"No message found with ClOrdID (tag 11) = {args.clordid}")
        return

    if args.seqnum:
        if args.archive:
            # Query archive
            cursor = store.conn.cursor()
            cursor.execute(
                "SELECT * FROM messages_archive WHERE sendercompid=? AND targetcompid=? AND msgseqnum=? ORDER BY archived_at",
                (sender, target, args.seqnum),
            )
            rows = cursor.fetchall()
            if not rows:
                print("No archived messages found for that seqnum.")
            for row in rows:
                print(f"Archived at: {row[5]}, Original timestamp: {row[6]}")
                print(row[4])
                print("-" * 40)
        else:
            # Query current
            msg = store.get_message(store.beginstring, sender, target, args.seqnum)
            print_message(msg)
    else:
        # Show all messages for session
        if args.archive:
            cursor = store.conn.cursor()
            cursor.execute(
                "SELECT msgseqnum, message, archived_at FROM messages_archive WHERE sendercompid=? AND targetcompid=? ORDER BY msgseqnum, archived_at",
                (sender, target),
            )
            rows = cursor.fetchall()
            for row in rows:
                print(f"SeqNum: {row[0]}, Archived at: {row[2]}")
                print(row[1])
                print("-" * 40)
        else:
            cursor = store.conn.cursor()
            cursor.execute(
                "SELECT msgseqnum, message, timestamp FROM messages WHERE sendercompid=? AND targetcompid=? ORDER BY msgseqnum",
                (sender, target),
            )
            rows = cursor.fetchall()
            for row in rows:
                print(f"SeqNum: {row[0]}, Timestamp: {row[2]}")
                print(row[1])
                print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())