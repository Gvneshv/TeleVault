"""
Handles Telethon's NewMessage event — fired for every message that arriveson the account, both incoming and outgoing (including Saved Messages).

Flow per event:
  1. Resolve the text to store — either the message body or a synthesized call label for MessageActionPhoneCall service messages.
  2. Skip if there is nothing worth archiving (media-only, stickers, etc.).
  3. Extract the chat entity and upsert it into `chats`.
  4. Extract the sender entity (if any) and upsert it into `senders`.
  5. Insert the message into `messages`.

We call `await event.get_chat()` and `await event.get_sender()` rather than reading `event.chat` / `event.sender` directly.
The direct attributes are only populated when Telegram includes the full entity in the update packet, which isn't guaranteed — the async getters always fetch from cache or the server.
"""

import logging

from telethon import events
from telethon.tl.types import MessageActionPhoneCall

import db
from .helpers import get_chat_type, get_sender_fields, format_call_text

logger = logging.getLogger(__name__)


def register(client) -> None:
    """Attach the NewMessage handler to the given Telethon client."""

    @client.on(events.NewMessage)
    async def on_new_message(event: events.NewMessage.Event) -> None:
        """
        Persist an incoming or outgoing message to the database.

        Regular text messages are stored as-is.
        Call service messages (MessageActionPhoneCall) are stored with a synthesized label such as "[Missed call]" or "[Voice call · 2 min 17 sec]" so they appear meaningfully in the archive and can be flagged as deleted like any other row.

        All other service messages and media-only messages (stickers, photos, etc.) are skipped — out of scope for Phase 1.
        """
        message = event.message

        # --- Resolve the text to archive -----------------------------------
        # Call service messages have no `.message` text — their payload is in `.action` (a MessageActionPhoneCall).
        # We synthesize a readable label for those.
        # Everything else falls through to the raw message body.
        action = getattr(message, "action", None)
        if isinstance(action, MessageActionPhoneCall):
            text = format_call_text(action)
        else:
            # `message.message` is the raw text body; empty string for media-only messages, None for other service message types.
            text = message.message

        # --- Pre-flight guards ---------------------------------------------

        # Telethon can return None for chat_id on certain service messages or protocol edge cases.
        # Without a valid chat_id we can't satisfy the FK constraint in messages, so skip rather than error.
        if event.chat_id is None:
            logger.warning(
                "Skipping message %s with no chat_id in event %s.",
                message.id, event,
            )
            return

        # Skip anything we have no text for — media, stickers, unsupported service messages, etc.
        # Call labels produced above are truthy, so they pass this guard correctly.
        if not text:
            logger.debug(
                "Skipping non-text message %s in chat %s.",
                message.id, event.chat_id,
            )
            return

        # --- Persist -------------------------------------------------------
        try:
            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_type = get_chat_type(chat)
            chat_name = getattr(chat, "title", None) or getattr(chat, "first_name", None)
            # Strip leading '@' if Telegram includes it (it usually doesn't, but be safe).
            chat_username = (getattr(chat, "username", None) or "").lstrip("@") or None
            username, first_name, last_name = get_sender_fields(sender)

            conn = db.get_connection()

            # Upsert chat and sender before the message insert — both are FKs.
            db.queries.upsert_chat(
                conn,
                chat_id   = event.chat_id,
                name      = chat_name,
                chat_type = chat_type,
                username  = chat_username,
                commit    = False,
            )

            if event.sender_id is not None:
                db.queries.upsert_sender(
                    conn,
                    sender_id  = event.sender_id,
                    username   = username,
                    first_name = first_name,
                    last_name  = last_name,
                    commit     = False,
                )

            db.queries.insert_message(
                conn,
                tg_message_id = message.id,
                chat_id       = event.chat_id,
                sender_id     = event.sender_id,
                text          = text,
                date          = message.date,
            )

        except Exception:
            # Log and swallow — a single failed insert should never crash the listener.
            # The message will simply be absent from the archive.
            logger.exception(
                "Failed to archive message %s in chat %s.",
                message.id, event.chat_id,
            )