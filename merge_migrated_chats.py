"""
One-off script: apply every recorded chat_migrations mapping to existing rows.

Run this AFTER a chat_migrations row exists for a pair you want merged
(populated by either on_message.py's live detection or backfill.py's migrated_from_chat_id check).
Safe to run repeatedly - already-merged chats have no rows left under the old id, so re-running is a no-op for them.
"""
import logging
import sqlite3

from config import settings
from utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def merge_all(conn: sqlite3.Connection) -> None:
    migrations = conn.execute("SELECT old_chat_id, new_chat_id FROM chat_migrations").fetchall()

    for old_id, new_id in migrations:
        # OR IGNORE: in the unlikely case a tg_message_id collides between the old and new chat's history
        # (Telegram's migrated_from_max_id should prevent this, but don't let one bad row abort the whole merge), skip it and log rather than fail.
        cursor = conn.execute(
            "UPDATE OR IGNORE messages SET chat_id = ? WHERE chat_id = ?", (new_id, old_id)
        )
        moved = cursor.rowcount
        conn.commit()

        remaining = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE chat_id = ?", (old_id,)
        ).fetchone()[0]

        if remaining == 0:
            conn.execute("DELETE FROM chats WHERE chat_id = ?", (old_id,))
            conn.commit()
            logger.info(f"Merged chat {old_id} -> {new_id}: moved {moved} messages, old chat row removed.")
        else:
            logger.warning(
                f"Merged chat {old_id} -> {new_id}: moved {moved} messages, but {remaining} rows "
                f"could not be moved (tg_message_id collision) - old chat row kept for inspection."
            )


def main() -> None:
    setup_logging(log_level=settings.log_level, log_file=settings.log_file)
    conn = sqlite3.connect(settings.db_path)
    merge_all(conn)
    conn.close()


if __name__ == "__main__":
    main()