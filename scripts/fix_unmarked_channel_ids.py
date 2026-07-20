"""
One-off script: find chats/supergroups/channels stored under their raw (unmarked) chat_id - the backfill.py bug, fixed in this same batch - and merge them into their
correctly marked counterpart via the existing chat_migrations + merge_migrated_chats machinery.

Safe to run repeatedly: chats with no raw-ID duplicate are left untouched.
"""
import logging
import sqlite3

from config import settings
from utils.logging_setup import setup_logging
from scripts.merge_migrated_chats import merge_all
import db.queries as queries

logger = logging.getLogger(__name__)


def find_and_record(conn: sqlite3.Connection) -> int:
    """Detect raw-ID/marked-ID duplicate pairs and record them in chat_migrations."""
    rows = conn.execute(
        "SELECT chat_id, chat_type FROM chats WHERE chat_type IN ('supergroup', 'channel') AND chat_id > 0"
    ).fetchall()

    found = 0
    for raw_id, _chat_type in rows:
        marked_id = int(f"-100{raw_id}")
        exists = conn.execute(
            "SELECT 1 FROM chats WHERE chat_id = ?", (marked_id,)
        ).fetchone()
        if exists:
            queries.record_chat_migration(conn, old_chat_id=raw_id, new_chat_id=marked_id)
            found += 1
        else:
            logger.warning(
                f"chat_id {raw_id} looks unmarked but has no marked counterpart "
                f"({marked_id}) yet - probably only ever backfilled, never seen live. "
                f"Renaming in place instead of merging."
            )
            conn.execute("UPDATE chats SET chat_id = ? WHERE chat_id = ?", (marked_id, raw_id))
            conn.execute("UPDATE messages SET chat_id = ? WHERE chat_id = ?", (marked_id, raw_id))
            conn.commit()
    return found


def main() -> None:
    setup_logging(log_level=settings.log_level, log_file=settings.log_file)
    conn = sqlite3.connect(settings.db_path)
    n = find_and_record(conn)
    logger.info(f"Recorded {n} raw-ID/marked-ID pairs for merging.")
    merge_all(conn)
    conn.close()


if __name__ == "__main__":
    main()