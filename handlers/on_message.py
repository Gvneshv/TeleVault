"""
Handles Telethon's NewMessage event - fired for every message that arrives on the account, both incoming and outgoing (including Saved Messages).
 
Flow per event:
  1. Extract the chat entity and upsert it into `chats`.
  2. Extract the sender entity (if any) and upsert it into `senders`.
  3. Insert the message into `messages`.
 
We call `await event.get_chat()` and `await event.get_sender()` rather than reading `event.chat` / `event.sender` directly.
The direct attributes are only populated when Telegram includes the full entity in the update packet,
which isn't guaranteed - the async getters always fetch from cache or the server if needed.
"""

import logging
from telethon import events

import db
from handlers.helpers import get_chat_type, get_sender_fields
from telethon.tl.types import MessageActionPhoneCall
from .helpers import format_call_text   # add to existing helpers import line


logger = logging.getLogger(__name__)


def register(client) -> None:
    """
    Attach the NewMessage handler to the given Telethon client.
    """

    @client.on(events.NewMessage)
    async def on_new_message(event: events.NewMessage.Event) -> None:
        """
        Persist an incoming or outgoing message to the database.
 
        Skips messages with no text content (stickers, photos, etc.) — those are out of scope for Phase 1 and would store an empty/null row.
        """
        # Resolve the stored text value.
        # Regular messages carry their content in `message.message`.
        # Call service messages carry no text — instead their `action` field is a MessageActionPhoneCall.
        # We synthesize a label for those so they appear meaningfully in the archive and can be deleted/flagged like any other row.
        action = getattr(event.message, "action", None)
        if isinstance(action, MessageActionPhoneCall):
            text = format_call_text(action)
        else:
            text = event.message.message  # None for non-text service messages


        # Telethon can return None for chat_id on certain service messages or protocol edge-cases. 
        # Without a valid chat_id we can't satisfy the FK constraint in messages, so skip rather than error.
        if event.chat_id is None:
            logger.warning(f"Skipping message {action.id} with no chat ID in event {event}.")
            return

        # Skip non-text content. For now, we archive text only.
        # `action.text` is an empty string (not None) for media-only messages, so we check for truthiness rather than `is not None`.
        if not action.text:
            logger.debug(f"Skipping non-text message {action.id} in chat {event.chat_id}.")

            return
        
        try:
            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_type = get_chat_type(chat)
            chat_name = getattr(chat, "title", None) or getattr(chat, "first_name", None)
            # Strip leading '@' if Telegram includes it (it usually doesn't, but be safe).
            chat_username = (getattr(chat, "username", None) or "").lstrip("@") or None
            username, first_name, last_name = get_sender_fields(sender)

            conn = db.get_connection()

            # Upsert chat and sender before inserting the message, since messages.chat_id and messages.sender_id are foreign keys.
            db.queries.upsert_chat(
                conn,
                chat_id     = event.chat_id,
                name        = chat_name,
                chat_type   = chat_type,
                username    = chat_username,
                commit      = False,
            )

            if event.sender_id is not None:
                db.queries.upsert_sender(
                    conn,
                    sender_id   = event.sender_id,
                    username    = username,
                    first_name  = first_name,
                    last_name   = last_name,
                    commit      = False,
                )

            db.queries.insert_message(
                conn,
                tg_message_id   = action.id,
                chat_id         = event.chat_id,
                sender_id       = event.sender_id,
                text            = action.text,
                date            = action.date,
            )
        except Exception:
            # Log and swallow - a single failed insert should never crash the listener.
            # The message will simply be absent from the archive.
            logger.exception(f"Failed to archive message {action.id} in chat {event.chat_id}.")