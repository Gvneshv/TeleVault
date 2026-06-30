"""
Small utilities shared across handler modules.
 
Kept here rather than in utils/ because these are tightly coupled to Telethon types and have no use outside the handlers package.
"""

import logging
from telethon import types
from telethon.tl.types import (
    MessageActionPhoneCall,
    PhoneCallDiscardReasonMissed,
    PhoneCallDiscardReasonBusy,
    PhoneCallDiscardReasonHangup,
    PhoneCallDiscardReasonDisconnect,
)

logger = logging.getLogger(__name__)


def get_chat_type(chat: object) -> str:
    """
    Map a Telethon chat entity to one of the four strings our schema accepts.
 
    Telethon represents chats as three distinct classes:
      - User    -> a direct / private conversation
      - Chat    -> a legacy group (up to 200 members, non-supergroup)
      - Channel -> both supergroups and broadcast channels share this class;
                  the megagroup flag distinguishes them
 
    The fallback logs a warning and returns 'group' so the INSERT doesn't violate the CHECK constraint while still surfacing unexpected types.
    """
    if isinstance(chat, types.User):
        return "private"
    if isinstance(chat, types.Chat):
        return "group"
    if isinstance(chat, types.Channel):
        return "supergroup" if chat.megagroup else "channel"
    
    logger.warning(f"Unknown chat entity type: {type(chat).__name__!r} — defaulting to 'group'.")

    return "group"


def get_sender_fields(sender: object | None) -> tuple[str | None, str | None, str | None]:
    """
    Extract (username, first_name, last_name) from a Telethon sender entity.
 
    Returns a triple of Nones when sender is None (e.g. broadcast channel posts, which have no individual author).
    """
    if sender is None:
        return None, None, None
    
    username = getattr(sender, "username", None)
    first_name = getattr(sender, "first_name", None)
    last_name = getattr(sender, "last_name", None)
    
    return username, first_name, last_name


def format_call_text(action: MessageActionPhoneCall) -> str:
    """
    Produce a human-readable archive label for a phone/video call service message, used as the stored `text` value in the messages table.

    Telegram does not deliver calls as regular messages — they arrive as MessageService events whose `action` field is MessageActionPhoneCall.
    TeleVault stores them as ordinary message rows with a synthetic text label so they appear naturally in the archive and can be flagged as
    deleted like any other message.

    Label format examples:
        [Video call · 4 min 32 sec]
        [Voice call · 1 min 08 sec]
        [Missed call]
        [Declined call]
        [Call ended (disconnected)]
        [Call · unknown outcome]

    Args:
        action: The MessageActionPhoneCall TL object from the service message.

    Returns:
        A bracket-wrapped string suitable for storage in messages.text.
    """
    call_type = "Video call" if getattr(action, "video", False) else "Voice call"
    reason = getattr(action, "reason", None)
    duration = getattr(action, "duration", None) or 0

    if isinstance(reason, PhoneCallDiscardReasonMissed):
        return "[Missed call]"

    if isinstance(reason, PhoneCallDiscardReasonBusy):
        return "[Declined call]"

    if isinstance(reason, PhoneCallDiscardReasonDisconnect):
        if duration:
            return f"[{call_type} · {_format_duration(duration)} (disconnected)]"
        return "[Call ended (disconnected)]"

    if isinstance(reason, PhoneCallDiscardReasonHangup) or reason is None:
        if duration:
            return f"[{call_type} · {_format_duration(duration)}]"
        # reason=None means the call was never answered / still ringing when the service message was created.
        # Treat as missed.
        return "[Missed call]"

    # Defensive fallback for any future reason types Telegram may add.
    return f"[{call_type} · unknown outcome]"
 
 
def _format_duration(seconds: int) -> str:
    """
    Format a call duration in seconds as a human-readable string.

    Examples:
        65  -> '1 min 05 sec'
        3   -> '3 sec'
        120 -> '2 min 00 sec'

    Zero-pads seconds when minutes are present, matching the style used in Telegram's own call history UI.
    """
    if seconds < 60:
        return f"{seconds} sec"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes} min {secs:02d} sec"