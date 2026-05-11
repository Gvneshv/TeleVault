"""
Defines and creates all database tables.
 
This module is run once on startup (via apply_schema). All statements use
CREATE TABLE IF NOT EXISTS, so re-running on an existing database is safe —
it simply does nothing if the tables are already there.
 
Table overview:
  - chats       : one row per Telegram chat/channel/DM
  - senders     : one row per Telegram user we've seen
  - messages    : every archived message
  - message_edits : full edit history for messages that were changed
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

_CREATE_CHATS = """
CREATE TABLE IF NOT EXISTS chats (
  chat_id       INTEGER PRIMARY KEY,
  name          TEXT,
  chat_type     TEXT    CHECK(chat_type IN ('group', 'supergroup', 'channel', 'private')),
  first_seen    DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_SENDERS = """
CREATE TABLE IF NOT EXISTS senders (
  sender_id     INTEGER PRIMARY KEY,
  username      TEXT,
  first_name    TEXT,
  last_name     TEXT,
  first_seen    DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Telegram assigns its own message ID, but only unique within a chat.
    -- We store both and enforce uniqueness on the pair (see index below).
    tg_message_id   INTEGER NOT NULL,
    chat_id         INTEGER NOT NULL,

    -- NULL for channels, where messages have no individual sender identity.
    sender_id       INTEGER,

    text            TEXT,
    date            DATETIME NOT NULL,

    -- Edit tracking
    is_edited       BOOLEAN DEFAULT FALSE,
    edited_at       DATETIME,

    -- Deletion tracking
    is_deleted      BOOLEAN DEFAULT FALSE,
    deleted_at      DATETIME,

    -- When the app receives and stores this message (not the same as date).
    archived_at     DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chat_id)   REFERENCES chats(chat_id),
    FOREIGN KEY (sender_id) REFERENCES senders(sender_id),
)
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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def apply_schema(conn: sqlite3.Connection) -> None:
    """
    Create all tables and indexes if they don't already exist.
    Safe to call on every startup
    """
    statements = [
        {"chats table":         _CREATE_CHATS},
        {"senders table":       _CREATE_SENDERS},
        {"messages table":      _CREATE_MESSAGES},
        {"messages index":      _CREATE_MESSAGES_INDEX},
        {"message_edits table": _CREATE_MESSAGE_EDITS},
        {"message_edits index": _CREATE_MESSAGE_EDITS_INDEX},
    ]

    with conn:      # 'with conn' is a transaction — all succeed or all roll back
        for label, sql in statements:
            logger.debug(f"Applying schema: {label}")
            conn.execute(sql)
    
    logger.info("Schema applied successfully.")