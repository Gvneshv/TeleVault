"""
Replaces message_deletions.deleted_by_inference's CHECK constraint values.

Migration 001 added the column with CHECK(... IN ('self', 'other', 'unknown')),
anticipating a private-chat sender_id/timing guess that was never built (see migration 001's corrected docstring).
After review, that guess was deliberately dropped:
Telegram allows any party to delete a message for everyone with no time limit and no record of who did it, so a guess there would be closer to a coin flip than a signal.

What ships instead: a channel-only inference.
Broadcast channels restrict deletion to admins (regular subscribers can't delete posts, including their own),
so a deletion there is a structural fact, not a guess.
See db/queries.py's flag_deleted() for where this is computed, and api/schemas/message.py's DeletionOut docstring for the full reasoning.

Why a table rebuild instead of a simpler ALTER:
    SQLite has no ALTER TABLE ... MODIFY CONSTRAINT.
    Changing a column's CHECK constraint requires the standard SQLite rebuild pattern:
    rename the old table, create the new one with the corrected constraint, copy the data across (remapping any now-invalid values), then drop the old table.
    Wrapped in a single transaction so it's all-or-nothing.

Run condition:
    Idempotent — checks the table's stored schema text in sqlite_master for 'channel_admin' before doing anything,
    so it's safe to run on every startup (matching the pattern in db/migrations/__init__.py's run_all()).
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def run(conn: sqlite3.Connection) -> None:
    """
    Apply migration 002: replace the deleted_by_inference CHECK constraint's allowed values with ('channel_admin', 'unknown').

    Any existing 'self'/'other' rows (there shouldn't be any — that logic was never implemented,
    see migration 001's docstring) are remapped to 'unknown' rather than dropped, so no deletion records are lost.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'message_deletions'"
    ).fetchone()
    current_sql = row[0] if row else ""

    if "channel_admin" in current_sql:
        logger.debug("Migration 002: constraint already updated, skipped.")
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
                    CHECK(deleted_by_inference IN ('channel_admin', 'unknown'))
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
            SELECT
                id, message_id, text_snapshot, deleted_at,
                CASE
                    WHEN deleted_by_inference IN ('self', 'other') THEN 'unknown'
                    ELSE deleted_by_inference
                END,
                inference_confidence
            FROM message_deletions_old
            """
        )

        conn.execute("DROP TABLE message_deletions_old")
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    logger.info(
        "Migration 002 applied: message_deletions.deleted_by_inference "
        "constraint updated to ('channel_admin', 'unknown')."
    )