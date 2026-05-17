"""
All database read and write operations for the app.
 
Design rules followed here:
  - Every function takes a connection as its first argument.
    No global state - callers control which connection is used.
  - All writes use 'with conn' (transaction context manager).
    If anything inside raises, the whole write is rolled back automatically.
  - INSERT OR IGNORE is used where duplicate arrivals are possible
    (e.g. Telegram sometimes re-delivers events on reconnect).
  - Functions return meaningful values (row ID, bool, fetched row) so callers
    can log or react without querying again.
"""

import logging
import sqlite3
from datetime import datetime, timezone


def _now() -> datetime:
    """
    Return the current UTC time as a timezone-aware datetime object.
    """
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chats
# ---------------------------------------------------------------------------

def upsert_chat(conn: sqlite3.Connection, chat_id: int, name: str | None, chat_type: str, username: str | None = None) -> None:
    """
    Insert a chat record if it doesn't exist yet.
    
    The ``username`` is the @handle - present for public groups and channels,
    None for private chats and legacy groups without a public link.
    Stored as-is without the leading '@' for cleaner querying.
 
    Existing rows are left untouched (INSERT OR IGNORE). Name/username
    changes over time are not tracked yet - that's a future feature.

    """
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO chats (chat_id, name, username, chat_type) VALUES (?, ?, ?, ?)",
            (chat_id, name, username, chat_type),
        )


# ---------------------------------------------------------------------------
# Senders
# ---------------------------------------------------------------------------


def upsert_sender(conn: sqlite3.Connection, sender_id: int, username: str | None, first_name: str | None, last_name: str | None) -> None:
    """
    Insert a sender record if it doesn't exist yet.
    Same rationale as upsert_chat - we preserve the first-seen identity.
    """
    with conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO senders (sender_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            """,
            (sender_id, username, first_name, last_name),
        )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def insert_message(conn: sqlite3.Connection, tg_message_id: int, chat_id: int, sender_id: int | None, text: str | None, date: datetime) -> int | None:
    """
    Store a new incoming or outgoing message.
 
    Returns the internal row ID (messages.id) on success, or None if the
    message was already present (INSERT OR IGNORE - safe on re-delivery)
    """
    with conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO messages (tg_message_id, chat_id, sender_id, text, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tg_message_id, chat_id, sender_id, text, date),
        )

    row_id = cursor.lastrowid if cursor.rowcount > 0 else None

    if row_id:
        logger.debug(
            f"Inserted message {tg_message_id} from chat {chat_id} -> internal id {row_id}"
        )
    else:
        logger.debug(
            f"Message {tg_message_id} in chat {chat_id} already exists - skipped."
        )
    
    return row_id


def flag_deleted(conn: sqlite3.Connection, tg_message_id: int, chat_id: int, deleted_at: datetime | None = None) -> bool:
    """
    Mark a message as deleted.
 
    Telegram's MessageDeleted event gives the message ID and chat ID,
    but not the message content - that's already in our DB. We just flip
    the flag and record when the deletion was detected.
 
    Returns True if a row was updated, False if the message wasn't in our DB.
    (We may not have it if the app wasn't running when it was sent.)
    """
    ts = deleted_at or _now()

    with conn:
        cursor = conn.execute(
            """
            UPDATE messages
            SET is_deleted = TRUE, deleted_at = ?
            WHERE tg_message_id = ? AND chat_id = ? AND is_deleted = FALSE
            """,
            (ts, tg_message_id, chat_id),
        )
    

    found = cursor.rowcount > 0

    if found:
        logger.info(f"Flagged message {tg_message_id} in chat {chat_id} as deleted at {ts}.")
    else:
        logger.warning(
            f"Deletion event for message {tg_message_id} in chat {chat_id} "
            f"- not found in DB (possibly sent before the app was running)."
        )

    return found


def record_edit(conn: sqlite3.Connection, tg_message_id: int, chat_id: int, new_text: str | None, edited_at: datetime | None = None) -> bool:
    """
    Handle an edited message:
      1. Fetch the current text from messages (becomes old_text in the log).
      2. Insert a row into message_edits with old and new text.
      3. Update messages with the new text and mark is_edited = TRUE.
 
    Returns True on success, False if the message wasn't found in the DB.
    """
    ts = edited_at or _now()

    # Step 1: look up the current (pre-edit) state
    row = get_message(conn, tg_message_id, chat_id)

    if row is None:
        logger.warning(
            f"Edit event for message {tg_message_id} in chat {chat_id} "
            f"- not found in DB."
        )
        return False
    
    old_text = row["text"]
    internal_id = row["id"]

    with conn:
        # Step 2: log the edit to message_edits
        conn.execute(
            """
            INSERT INTO message_edits (message_id, old_text, new_text, edited_at)
            VALUES (?, ?, ?, ?)
            """,
            (internal_id, old_text, new_text, ts),
        )

        # Step 3: update the live text in messages
        conn.execute(
            """
            UPDATE messages
            SET text = ?, is_edited = TRUE, edited_at = ?
            WHERE id = ?
            """,
            (new_text, ts, internal_id),
        )
    
    logger.info(
        f"Recorded edit for message {tg_message_id} in chat {chat_id} "
        f"(internal id {internal_id})."
    )
    return True


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_message(conn: sqlite3.Connection, tg_message_id: int, chat_id: int) -> sqlite3.Row | None:
    """
    Fetch a single message row by its Telegram ID + chat ID.
    Returns a Row (dict-like) or None if not found.
    """
    cursor = conn.execute(
        """
        SELECT * FROM messages
        WHERE tg_message_id = ? AND chat_id = ?
        """,
        (tg_message_id, chat_id),
    )
    return cursor.fetchone()


def get_deleted_messages(conn: sqlite3.Connection, chat_id: int | None = None, limit: int = 100) -> list[sqlite3.Row]:
    """
    Retrieve deleted messages, optionally filtered by chat.
    Ordered newest-deleted first.

    Each row includes chat_name and chat_username from the joined chats table,
    useful for display without a second query.

    """
    if chat_id is not None:
        cursor = conn.execute(
            """
            SELECT m.*, c.name AS chat_name, c.username AS chat_username
            FROM messages m
            JOIN chats c ON m.chat_id = c.chat_id
            WHERE m.is_deleted = TRUE AND m.chat_id = ?
            ORDER BY m.deleted_at DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT m.*, c.name AS chat_name, c.username AS chat_username
            FROM messages m
            JOIN chats c ON m.chat_id = c.chat_id
            WHERE m.is_deleted = TRUE
            ORDER BY m.deleted_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    
    return cursor.fetchall()


def get_edit_history(conn: sqlite3.Connection, tg_message_id: int, chat_id: int) -> list[sqlite3.Row]:
    """
    Return the full edit history for a message, oldest edit first.
    """
    row = get_message(conn, tg_message_id, chat_id)
    if row is None:
        return []
    
    cursor = conn.execute(
        """
        SELECT * FROM message_edits
        WHERE message_id = ?
        ORDER BY edited_at ASC
        """,
        (row["id"],),
    )
    return cursor.fetchall()