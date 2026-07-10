"""
Widens message_deletions.deleted_by_inference's CHECK constraint to add 'self', for Saved Messages actor inference.

Migration 002 narrowed the constraint to ('channel_admin', 'unknown') after the original ('self', 'other', 'unknown')
from migration 001 turned out to have never been populated with 'self' or 'other'
(see 001's and 002's docstrings — that logic was never implemented, then deliberately dropped for ordinary private/group chats).

This migration reintroduces 'self', but for a narrower and much more reliable case than what was originally planned:
Saved Messages specifically (chat_id == the archiving account's own Telegram user ID),
where only the account owner has access at all — no ambiguity, unlike an ordinary private chat between two people.
See db/queries.py's flag_deleted() for where this is computed, and handlers/on_delete.py / main.py for how self_id reaches it.

Why a table rebuild instead of a simpler ALTER:
same reason as migration 002 — SQLite has no ALTER TABLE ... MODIFY CONSTRAINT,
so changing a CHECK constraint requires the standard rebuild pattern (rename, recreate, copy, drop), wrapped in one transaction.

Run condition: idempotent — checks the table's stored schema text in sqlite_master for "'self'" before doing anything, so it's safe to run on every startup.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def run(conn: sqlite3.Connection) -> None:
    """
    Apply migration 003: widen deleted_by_inference's CHECK constraint to ('channel_admin', 'self', 'unknown').
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'message_deletions'"
    ).fetchone()
    current_sql = row[0] if row else ""

    if "'self'" in current_sql:
        logger.debug("Migration 003: constraint already updated, skipped.")
        return

    try:
        conn.execute("ALTER TABLE message_deletions RENAME TO message_deletions_old")

        conn.execute(
            """
            CREATE TABLE message_deletions (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id             INTEGER NOT NULL,
                text_snapshot          TEXT,
                deleted_at             DATETIME,
                deleted_by_inference   TEXT
                    CHECK(deleted_by_inference IN ('channel_admin', 'self', 'unknown'))
                    DEFAULT 'unknown',
                inference_confidence   TEXT,
                FOREIGN KEY (message_id) REFERENCES messages(id)
            )
            """
        )

        conn.execute(
            """
            INSERT INTO message_deletions
                (id, message_id, text_snapshot, deleted_at, deleted_by_inference, inference_confidence)
            SELECT id, message_id, text_snapshot, deleted_at, deleted_by_inference, inference_confidence
            FROM message_deletions_old
            """
        )

        conn.execute("DROP TABLE message_deletions_old")
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    logger.info(
        "Migration 003 applied: message_deletions.deleted_by_inference constraint updated to ('channel_admin', 'self', 'unknown')."
    )