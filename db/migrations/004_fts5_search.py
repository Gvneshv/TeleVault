"""
Adds FTS5 full-text search over messages.text (external content table),
replacing the LOWER_UNICODE() + LIKE '%...%' substring search used in read_queries.py's get_messages() and get_chat_messages().

Tokenizer choice: trigram, not the default.
The default FTS5 tokenizer matches whole words/prefixes only - a real behaviour change from what users have now, not just a performance detail.
The trigram tokenizer indexes overlapping 3-character sequences instead, which keeps the same "substring anywhere,
including mid-word" search behaviour as the current LIKE '%...%' - confirmed against Cyrillic text with case_sensitive=0 before writing this migration,
since that's exactly what LOWER_UNICODE() was built to handle.
One real trade-off: search terms shorter than 3 characters won't match well under trigram indexing.

External content table (content='messages', content_rowid='id') - the FTS index doesn't duplicate message text,
it stays in sync with the messages table via the three triggers below.
All three (insert/update/delete) are required together for an external content table; SQLite's own FTS5 docs cover why.

Requires SQLite compiled with FTS5 and the trigram tokenizer (>= 3.34.0, Dec 2020).
Checked explicitly below with a clear error instead of a confusing generic failure if unsupported.
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def run(conn: sqlite3.Connection) -> None:
    """
    Apply migration 004: create messages_fts, its sync triggers, and backfill existing rows (triggers only cover future changes).
    """
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'messages_fts'"
    ).fetchone()
    if exists:
        logger.debug("Migration 004: messages_fts already exists, skipped.")
        return

    try:
        conn.execute(
            "CREATE VIRTUAL TABLE messages_fts USING fts5("
            "text, content='messages', content_rowid='id', "
            "tokenize='trigram case_sensitive 0')"
        )
    except sqlite3.OperationalError as exc:
        raise RuntimeError(
            "Could not create the FTS5 trigram virtual table - this SQLite "
            "build may not support FTS5 or the trigram tokenizer (needs "
            f"SQLite >= 3.34.0 with FTS5 compiled in). Original error: {exc}"
        ) from exc

    try:
        conn.execute(
            """
            CREATE TRIGGER messages_fts_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, text) VALUES (new.id, new.text);
            END
            """
        )
        conn.execute(
            """
            CREATE TRIGGER messages_fts_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.id, old.text);
            END
            """
        )
        conn.execute(
            """
            CREATE TRIGGER messages_fts_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.id, old.text);
                INSERT INTO messages_fts(rowid, text) VALUES (new.id, new.text);
            END
            """
        )

        # Backfill existing rows - the triggers above only cover changes from here on.
        conn.execute(
            "INSERT INTO messages_fts(rowid, text) SELECT id, text FROM messages WHERE text IS NOT NULL"
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    logger.info(
        "Migration 004 applied: messages_fts (FTS5, trigram tokenizer) created and backfilled."
    )