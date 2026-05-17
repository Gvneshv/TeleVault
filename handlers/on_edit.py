"""
Handles Telethon's MessageEdited event - fired when a message's text is changed by its sender.
 
Why we bother archiving edits:
  A common pattern is editing -> deleting. Someone writes something, edits it
  (maybe to soften it), then deletes it. Without the edit history, the archive
  shows only the final text before deletion. With it, you get the full picture.
 
Flow per event:
  1. Confirm the edited message has text (skip media caption changes for now).
  2. Call queries.record_edit, which:
       a. Fetches the current text from the DB (becomes old_text).
       b. Writes a row to message_edits with old -> new.
       c. Updates messages with the new text and sets is_edited = TRUE.
  3. Ensure the chat and sender are in the DB first, same as on_message.
     (Edge case: a message could be edited in a chat we somehow missed
     archiving — the FK would fail without the upsert guard.)
"""

import logging
from telethon import events

import db
from handlers.helpers import get_chat_type, get_sender_fields

logger = logging.getLogger(__name__)


def register(client) -> None:
    """
    Attach the MessageEdited handler to the given Telethon client.
    """

    @client.on(events.MessageEdited)
    async def on_message_edited(event: events.MessageEdited.Event) -> None:
        """
        Record a message edit: snapshot old text, store new text, update the live row in `messages`.
        """
        message = event.message

        # Same rationale as on_message — skip non-text edits for now.
        if not message.text:
            logger.debug(f"Skipping non-text edit for message {message.id} in chat {event.chat_id}.")
            return
        
        try:
            chat = await event.get_chat()
            sender = await event.get_sender()

            chat_type = get_chat_type(chat)
            chat_name = getattr(chat, "title", None) or getattr(chat, "first_name", None)
            username, first_name, last_name = get_sender_fields(sender)

            conn = db.get_connection()

            # Guard: ensure the chat and sender rows exist. If this edit
            # arrives for a message we never archived (e.g. TeleVault was
            # offline when it was sent), the upserts create the parent rows
            # so the FK constraints don't blow up.
            db.queries.upsert_chat(conn, chat_id=event.chat_id, name=chat_name, chat_type=chat_type)

            if event.sender_id is None:
                db.queries.upsert_sender(conn, sender_id=event.sender_id, username=username, first_name=first_name, last_name=last_name)
            
            # edit_date is set by Telegram when the message is edited.
            # Fall back to None - queries.record_edit uses _now() in that case.
            edit_date = getattr(message, "edit_date", None)

            found = db.queries.record_edit(conn, tg_message_id=message.id, chat_id=event.chat_id, new_text=message.text, edited_at=edit_date)

            if not found:
                # The original message isn't in our DB - insert it now with
                # the current (post-edit) text. Not ideal, but better than
                # having no record of this message at all.
                logger.info(
                    f"Edit received for unknown message {message.id} in chat {event.chat_id} "
                    f"— inserting current version as a new record."
                )
                db.queries.insert_message(conn, tg_message_id=message.id, chat_id=event.chat_id, sender_id=event.sender_id, text=message.text, date=message.date)
        except Exception:
            logger.exception(
                f"Failed to record edit for message {message.id} in chat {event.chat_id}."
            )