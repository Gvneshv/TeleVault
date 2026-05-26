"""
Defines and creates all database tables.
 
This module is run once on startup (via apply_schema). All statements use
CREATE TABLE IF NOT EXISTS, so re-running on an existing database is safe -
it simply does nothing if the tables are already there.
 
Table overview:
  - chats       : one row per Telegram chat/channel/DM
  - senders     : one row per Telegram user we've seen
  - messages    : every archived message
  - message_edits : full edit history for messages that were changed
  - message_deletions : full deletion history for messages that were deleted

Schema change log:
  v1 (initial) : chats, senders, messages, message_edits
  v2           : chats.username added for @handle cross-referencing
  v3           : message_deletions table added (mirrors message_edits)
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL statements
#
# Rules for these strings:
#   1. No inline SQL comments (-- ...) inside the DDL body.
#      On Windows, Git's CRLF conversion can place a bare \r before a comment,
#      which confuses SQLite's parser and produces "near ')': syntax error".
#      All explanatory notes live here, above each string, as Python comments.
#   2. BOOLEAN columns use INTEGER DEFAULT 0 / 1 - not FALSE / TRUE.
#      TRUE/FALSE as SQL keywords were only made reliable in SQLite 3.23.0.
#      INTEGER 0/1 works on every SQLite version.
# ---------------------------------------------------------------------------

# chat_type is restricted to four known values via a CHECK constraint.
# username stores the @handle for groups/channels; NULL for private chats
# and legacy groups that have no public link.
_CREATE_CHATS = """
CREATE TABLE IF NOT EXISTS chats (
  chat_id       INTEGER PRIMARY KEY,
  name          TEXT,
  username      TEXT,
  chat_type     TEXT CHECK(chat_type IN ('group', 'supergroup', 'channel', 'private')),
  first_seen    DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Stores Telegram user identity at the time first encountered.
# username may be NULL (not every user sets a @handle).
_CREATE_SENDERS = """
CREATE TABLE IF NOT EXISTS senders (
  sender_id     INTEGER PRIMARY KEY,
  username      TEXT,
  first_name    TEXT,
  last_name     TEXT,
  first_seen    DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# Core archive table.
# tg_message_id is Telegram's ID, which is only unique within a single chat,
# so the uniqueness constraint is on the (tg_message_id, chat_id) pair.
# sender_id is NULL for channel posts (no individual author).
# archived_at records when TeleVault stored the row, distinct from date
# (when Telegram says the message was sent).
_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_message_id   INTEGER NOT NULL,
    chat_id         INTEGER NOT NULL,
    sender_id       INTEGER,
    text            TEXT,
    date            DATETIME NOT NULL,
    is_edited       INTEGER DEFAULT 0,
    edited_at       DATETIME,
    is_deleted      INTEGER DEFAULT 0,
    deleted_at      DATETIME,
    archived_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id)   REFERENCES chats(chat_id),
    FOREIGN KEY (sender_id) REFERENCES senders(sender_id)
);
"""

# A compound unique index on (tg_message_id, chat_id) is critical.
# Telegram reuses message IDs across different chats, so tg_message_id alone
# is not unique globally. This index also speeds up deletion lookups, where
# the app receives a (message_id, chat_id) pair and need to find the right row fast.
_CREATE_MESSAGES_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_tg_id_chat ON messages(tg_message_id, chat_id);
"""

# Stores the full before/after text each time a message is edited.
# This gives a complete revision history, not just "was it ever edited".
# Linked to messages.id (the app internal ID, not Telegram's).
_CREATE_MESSAGE_EDITS = """
CREATE TABLE IF NOT EXISTS message_edits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER NOT NULL,
    old_text        TEXT,
    new_text        TEXT,
    edited_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id)
)
"""

# Index for quickly fetching all edits for a given message.
_CREATE_MESSAGE_EDITS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_message_edits_message_id ON message_edits(message_id);
"""

# Mirrors message_edits but for deletions.
# Stores a snapshot of the text at deletion time so the record is
# self-contained - useful even if messages.text is later modified.
# deleted_at is passed explicitly from Python (local time) rather than
# relying on SQLite's DEFAULT CURRENT_TIMESTAMP, which is always UTC.
_CREATE_MESSAGE_DELETIONS = """
CREATE TABLE IF NOT EXISTS message_deletions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER NOT NULL,
    text_snapshot   TEXT,
    deleted_at      DATETIME,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);
"""

# Index for quickly fetching all deletions for a given message.
_CREATE_MESSAGE_DELETIONS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_message_deletions_message_id ON message_deletions(message_id);
"""

_STATEMENTS = [
        ("chats table",         _CREATE_CHATS),
        ("senders table",       _CREATE_SENDERS),
        ("messages table",      _CREATE_MESSAGES),
        ("messages index",      _CREATE_MESSAGES_INDEX),
        ("message_edits table", _CREATE_MESSAGE_EDITS),
        ("message_edits index", _CREATE_MESSAGE_EDITS_INDEX),
        ("message_deletions table", _CREATE_MESSAGE_DELETIONS),
        ("message_deletions index", _CREATE_MESSAGE_DELETIONS_INDEX),
    ]


def _clean(sql: str) -> str:
    """
    Strip stray carriage returns before passing SQL to SQLite.
 
    On Windows, Python source files checked out via Git often contain CRLF
    line endings, which means triple-quoted string literals contain \\r\\n.
    SQLite's parser can stumble on the bare \\r character inside DDL, producing
    misleading 'near ): syntax error' messages. Stripping \\r is always safe.
    """
    return sql.replace("\r\n", "\n").replace("\r", "\n")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def apply_schema(conn: sqlite3.Connection) -> None:
    """
    Create all tables and indexes if they don't already exist.
    Safe to call on every startup

    Each statement is executed individually and committed immediately.
    Wrapping DDL in a transaction context manager (with conn:) can cause
    failures on Python 3.12+ where the context manager starts an explicit
    transaction - SQLite has constraints on DDL inside certain transaction
    states. Explicit per-statement commits sidestep this entirely.
    """
    for label, sql in _STATEMENTS:
        cleaned = _clean(sql)
        logger.debug(f"Applying schema {label}")
        try:
            conn.execute(cleaned)
            conn.commit()
        except sqlite3.OperationalError as exc:
            # Re-raise with context: which statement failed and its exact SQL,
            # so the error message is actionable rather than just a line number.
            raise sqlite3.OperationalError(
                f"Schema error while applying '{label}'.\n"
                f"SQL attempted:\n{cleaned}\n"
                f"Original error: {exc}"
            ) from exc
    
    logger.info("Schema applied successfully.")