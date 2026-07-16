"""
Defines and creates all database tables.
 
This module is run once on startup (via apply_schema).
All statements use CREATE TABLE IF NOT EXISTS, so re-running on an existing database is safe - it simply does nothing if the tables are already there.
 
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
  v4           : read-path indexes on messages (chat_id+date, date, sender_id, partial indexes on is_deleted/is_edited) - added once list views got slow at real scale (Phase 3); the only prior messages index served write-path dedup, not any read query
  v5           : chat_migrations table - maps an old (pre-migration) chat_id to its canonical new chat_id.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL statements
#
# Rules for these strings:
#   1. No inline SQL comments (-- ...) inside the DDL body.
#      On Windows, Git's CRLF conversion can place a bare \r before a comment, which confuses SQLite's parser and produces "near ')': syntax error".
#      All explanatory notes live here, above each string, as Python comments.
#   2. BOOLEAN columns use INTEGER DEFAULT 0 / 1 - not FALSE / TRUE.
#      TRUE/FALSE as SQL keywords were only made reliable in SQLite 3.23.0.
#      INTEGER 0/1 works on every SQLite version.
# ---------------------------------------------------------------------------

# chat_type is restricted to four known values via a CHECK constraint.
# username stores the @handle for groups/channels; NULL for private chats and legacy groups that have no public link.
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
# tg_message_id is Telegram's ID, which is only unique within a single chat, so the uniqueness constraint is on the (tg_message_id, chat_id) pair.
# sender_id is NULL for channel posts (no individual author).
# archived_at records when TeleVault stored the row, distinct from date (when Telegram says the message was sent).
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
# Telegram reuses message IDs across different chats, so tg_message_id alone is not unique globally.
# This index also speeds up deletion lookups, where the app receives a (message_id, chat_id) pair and need to find the right row fast.
_CREATE_MESSAGES_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_tg_id_chat ON messages(tg_message_id, chat_id);
"""

# Read-path indexes - added once list views started running slowly at real scale (Phase 3, ~460k rows).
# None of these existed before;
# the only index above serves the write-path dedup check, not any of the read queries in db/read_queries.py.
# chat_id + date covers get_chat_messages() (WHERE chat_id = ? ORDER BY date DESC) and get_chats()' per-chat aggregation directly.
_CREATE_MESSAGES_CHAT_DATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date DESC);
"""

# Plain date covers get_messages()' global feed ORDER BY date DESC when there's no chat_id filter (the common case for the Messages view).
_CREATE_MESSAGES_DATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date DESC);
"""

# Covers the sender_id filter in get_messages()/get_chat_messages().
_CREATE_MESSAGES_SENDER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
"""

# Partial indexes for is_deleted/is_edited - both are a small fraction of all rows in a real archive
# (e.g. 52 deleted and 359 edited out of 458931 total, from actual testing),
# so a partial index only needs to cover that fraction instead of the whole table like a plain index would.
# This is what makes the Deleted view and the Messages view's "edited only" filter fast instead of a full table scan for a handful of matching rows.
_CREATE_MESSAGES_DELETED_PARTIAL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_is_deleted_partial ON messages(chat_id, date DESC) WHERE is_deleted = 1;
"""

_CREATE_MESSAGES_EDITED_PARTIAL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_is_edited_partial ON messages(chat_id, date DESC) WHERE is_edited = 1;
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
# Stores a snapshot of the text at deletion time so the record is self-contained - useful even if messages.text is later modified.
# deleted_at is passed explicitly from Python (local time) rather than relying on SQLite's DEFAULT CURRENT_TIMESTAMP, which is always UTC.
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

# Populated when a basic group upgrades to a supergroup, detected either live (MessageActionChatMigrateTo/MessageActionChannelMigrateFrom service messages)
# or during backfill (ChannelFull.migrated_from_chat_id).
# Read by queries.resolve_chat_id() so every future write is canonicalized automatically.
_CREATE_CHAT_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS chat_migrations (
  old_chat_id   INTEGER PRIMARY KEY,
  new_chat_id   INTEGER NOT NULL,
  migrated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


_STATEMENTS = [
        ("chats table",         _CREATE_CHATS),
        ("chat_migrations table", _CREATE_CHAT_MIGRATIONS),
        ("senders table",       _CREATE_SENDERS),
        ("messages table",      _CREATE_MESSAGES),
        ("messages index",      _CREATE_MESSAGES_INDEX),
        ("messages chat_date index",      _CREATE_MESSAGES_CHAT_DATE_INDEX),
        ("messages date index",          _CREATE_MESSAGES_DATE_INDEX),
        ("messages sender index",        _CREATE_MESSAGES_SENDER_INDEX),
        ("messages deleted partial index", _CREATE_MESSAGES_DELETED_PARTIAL_INDEX),
        ("messages edited partial index",  _CREATE_MESSAGES_EDITED_PARTIAL_INDEX),
        ("message_edits table", _CREATE_MESSAGE_EDITS),
        ("message_edits index", _CREATE_MESSAGE_EDITS_INDEX),
        ("message_deletions table", _CREATE_MESSAGE_DELETIONS),
        ("message_deletions index", _CREATE_MESSAGE_DELETIONS_INDEX),
    ]


def _clean(sql: str) -> str:
    """
    Strip stray carriage returns before passing SQL to SQLite.
 
    On Windows, Python source files checked out via Git often contain CRLF line endings, which means triple-quoted string literals contain \\r\\n.
    SQLite's parser can stumble on the bare \\r character inside DDL, producing misleading 'near ): syntax error' messages.
    Stripping \\r is always safe.
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
    Wrapping DDL in a transaction context manager (with conn:) can cause failures on Python 3.12+ where the context manager starts an explicit transaction
    - SQLite has constraints on DDL inside certain transaction states.
    Explicit per-statement commits sidestep this entirely.
    """
    for label, sql in _STATEMENTS:
        cleaned = _clean(sql)
        logger.debug(f"Applying schema {label}")
        try:
            conn.execute(cleaned)
            conn.commit()
        except sqlite3.OperationalError as exc:
            # Re-raise with context: which statement failed and its exact SQL, so the error message is actionable rather than just a line number.
            raise sqlite3.OperationalError(
                f"Schema error while applying '{label}'.\n"
                f"SQL attempted:\n{cleaned}\n"
                f"Original error: {exc}"
            ) from exc
    
    from db.migrations import run_all
    run_all(conn)
    logger.info("Schema applied successfully.")