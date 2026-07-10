"""
Handles Telethon's MessageDeleted event - fired when one or more messages are removed from a chat.
 
The important protocol limitation documented here:
 
    Telegram's server sends two different update types for deletions:
      - updateDeleteMessages        (private chats, legacy groups)
      - updateDeleteChannelMessages (channels, supergroups)
 
    Only the channel variant includes the chat ID.
    For private chats and groups, Telegram tells us WHICH messages were deleted but not WHERE.
    This is not a Telethon bug - it's the raw MTProto protocol.
 
Consequences and how we handle them:
  - event.chat_id is set   -> standard flag_deleted(chat_id, msg_id)
  - event.chat_id is None  -> fall back to flagging by message ID only,
    which may match the same tg_message_id in multiple chats (rare but possible). Logged.

self_id (passed in via register()) is the archiving account's own Telegram user ID,
forwarded to flag_deleted() for Saved Messages detection — see db/queries.py's flag_deleted() docstring for why that's the one private chat where the deletion actor can be known for certain.
"""

import logging
from telethon import events

import db

logger = logging.getLogger(__name__)


def register(client, self_id: int) -> None:
    """
    Attach the MessageDeleted handler to the given Telethon client.
    """

    @client.on(events.MessageDeleted)
    async def on_message_deleted(event: events.MessageDeleted.Event) -> None:
        """
        Flag deleted messages in the database.
 
        `event.deleted_ids` is always a list - Telegram can batch-delete multiple messages in one update (e.g. clearing a chat history).
        """
        chat_id = event.chat_id             # None for private/group deletions
        deleted_ids = event.deleted_ids     # Always a list (list[int])

        if not deleted_ids:
            return
        
        conn = db.get_connection()

        if chat_id is not None:
            # Happy path: we know exactly which chat these belong to
            for msg_id in deleted_ids:
                try:
                    db.queries.flag_deleted(conn, tg_message_id=msg_id, chat_id=chat_id, self_id=self_id)
                except Exception:
                    logger.exception(f"Failed to flag deletion for message {msg_id} in chat {chat_id}.")
        else:
            # Degraded path: private chat or legacy group deletion.
            # We have the message IDs but not the chat.
            # Flag whatever we can find by ID alone and log the ambiguity.
            logger.debug(
                f"Deletion event with no chat_id - attempting fallback for {len(deleted_ids)} message(s)."
            )
            for msg_id in deleted_ids:
                try:
                    _flag_deleted_without_chat(conn, msg_id, self_id)
                except Exception:
                    logger.exception(f"Failed fallback deletion flag for message {msg_id}.")



def _flag_deleted_without_chat(conn, tg_message_id: int, self_id: int) -> None:
    """
    Flag a message as deleted when the chat ID is unknown.
 
    Searches by tg_message_id alone and flags all matching rows.
    In practice the same numeric message ID rarely exists in multiple chats simultaneously, but it's theoretically possible since Telegram scopes IDs per chat.

    When multiple matches are found, we cross-reference the chats table for the stored name and @username.
    This doesn't resolve the ambiguity automatically (the protocol gives us nothing to go on), but it makes the log entry human-readable so you can tell at a glance which chats were affected rather than staring at a list of raw IDs.
 
    If the message isn't in the DB at all (sent before TeleVault was running), queries.flag_deleted already logs a warning - nothing extra needed here.
    """
    from datetime import datetime, timezone

    # Written as concatenated single-line strings to avoid CRLF issues on Windows - multi-line triple-quoted strings can contain \r characters after Git checkout, which SQLite's parser rejects mid-statement.
    # Also uses is_deleted = 0 (not FALSE) to match the INTEGER schema column.
    cursor = conn.execute(
        "SELECT m.tg_message_id, m.chat_id, c.name AS chat_name, c.username AS chat_username"
        " FROM messages m"
        " LEFT JOIN chats c ON m.chat_id = c.chat_id"
        " WHERE m.tg_message_id = ? AND m.is_deleted = 0",
        (tg_message_id,),
    )
    rows = cursor.fetchall()

    if not rows:
        logger.warning(
            f"Deletion fallback: message {tg_message_id} not found in DB (possibly sent before TeleVault was running)."
        )
        return
    
    if len(rows) > 1:
        # Build a readable description of each candidate chat.
        candidates = ", ".join(
            _format_chat(r["chat_id"], r["chat_name"], r["chat_username"])
            for r in rows
        )
        logger.warning(
            f"Deletion fallback: message ID {tg_message_id} matched {len(rows)} rows "
            f"({candidates}) - flagged all. Cannot determine which chat without "
            f"a chat_id in the deletion event (MTProto limitation)."
        )

    for row in rows:
        logger.info(
            f"Deletion fallback: flagging message {tg_message_id} in {_format_chat(row['chat_id'], row['chat_name'], row['chat_username'])}."
        )
        db.queries.flag_deleted(
            conn, 
            tg_message_id=row["tg_message_id"], 
            chat_id=row["chat_id"], 
            deleted_at=datetime.now(timezone.utc),
            self_id=self_id,
        )



def _format_chat(chat_id: int, name: str | None, username: str | None) -> str:
    """
    Return a readable chat label like 'My Group (@mygroup, id=123456)'.
    """
    parts = []
    if username:
        parts.append(f"@{username}")
    
    parts.append(f"id={chat_id}")
    label = name or "unnamed"
    
    return f"{label!r} ({', '.join(parts)})"