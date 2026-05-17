"""
Handles Telethon's MessageDeleted event — fired when one or more messages
are removed from a chat.
 
The important protocol limitation documented here:
 
    Telegram's server sends two different update types for deletions:
      - updateDeleteMessages        (private chats, legacy groups)
      - updateDeleteChannelMessages (channels, supergroups)
 
    Only the channel variant includes the chat ID. For private chats and
    groups, Telegram tells us WHICH messages were deleted but not WHERE.
    This is not a Telethon bug - it's the raw MTProto protocol.
 
Consequences and how we handle them:
  - event.chat_id is set   -> standard flag_deleted(chat_id, msg_id)
  - event.chat_id is None  -> fall back to flagging by message ID only,
    which may match the same tg_message_id in multiple chats (rare but possible). Logged.
"""

import logging
from telethon import events

import db

logger = logging.getLogger(__name__)


def register(client) -> None:
    """
    Attach the MessageDeleted handler to the given Telethon client.
    """

    @client.on(events.MessageDeleted)
    async def on_message_deleted(event: events.MessageDeleted.Event) -> None:
        """
        Flag deleted messages in the database.
 
        `event.deleted_ids` is always a list - Telegram can batch-delete
        multiple messages in one update (e.g. clearing a chat history).
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
                    db.queries.flag_deleted(conn, tg_message_id=msg_id, chat_id=chat_id)
                except Exception:
                    logger.exception(f"Failed to flag deletion for message {msg_id} in chat {chat_id}.")
        else:
            # Degraded path: private chat or legacy group deletion.
            # We have the message IDs but not the chat. Flag whatever we can
            # find by ID alone and log the ambiguity.
            logger.debug(
                f"Deletion event with no chat_id — "
                f"attempting fallback for {len(deleted_ids)} message(s)."
            )
            for msg_id in deleted_ids:
                try:
                    _flag_deleted_without_chat(conn, msg_id)
                except Exception:
                    logger.exception(f"Failed fallback deletion flag for message {msg_id}.")



def _flag_deleted_without_chat(conn, tg_message_id: int) -> None:
    """
    Flag a message as deleted when the chat ID is unknown.
 
    Searches by tg_message_id alone and flags all matching rows. In practice
    the same numeric message ID rarely exists in multiple chats simultaneously,
    but it's theoretically possible since Telegram scopes IDs per chat.
 
    If the message isn't in the DB at all (sent before TeleVault was running),
    queries.flag_deleted already logs a warning — nothing extra needed here.
    """
    from datetime import datetime, timezone

    # Reach into SQLite directly for this non-standard query.
    # It doesn't belong in queries.py because it's a fallback for a
    # protocol limitation, not a normal operation.
    cursor = conn.execute(
        "SELECT tg_message_id, chat_id FROM messages WHERE tg_message_id = ? AND is_deleted = FALSE",
        (tg_message_id,)
    )
    rows = cursor.fetchall()

    if not rows:
        logger.warning(
            f"Deletion fallback: message {tg_message_id} not found in DB "
            f"(possibly sent before TeleVault was running)."
        )
        return
    
    if len(rows) > 1:
        logger.warning(
            f"Deletion fallback: message ID {tg_message_id} matched {len(rows)} rows "
            f"across different chats — flagging all of them."
        )

    for row in rows:
        db.queries.flag_deleted(conn, tg_message_id=row["tg_message_id"], chat_id=row["chat_id"], deleted_at=datetime.now(timezone.utc))