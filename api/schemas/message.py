"""
Response models for message-related endpoints.
 
Model hierarchy:
    SenderOut           - sender identity, embedded in messages
    EditOut             - one entry in a message's edit history
    DeletionOut         - deletion record with inference metadata
    MessageOut          - one row in a paginated message list
    MessageDetail       - full message with edit history + deletion record, returned by GET /api/messages/{id}
"""

from typing import Literal
from pydantic import BaseModel, Field

from .chat import ChatSummary


class SenderOut(BaseModel):
    """
    Sender identity embedded inside message responses.
 
    `display_name` is the user-defined label override (Phase 3 feature).
    When present it takes precedence over first_name/last_name in the UI.
    The field is included now so the API contract is stable before the feature is built - the backend simply returns None until then.
    """

    sender_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = Field(None, description="User-defined label override for this sender. Phase 3 feature.")

    @property
    def resolved_name(self) -> str:
        """
        Best human-readable name available, in priority order:
        display_name -> first+last -> first -> @username -> str(sender_id)
        """
        if self.display_name:
            return self.display_name
        parts = filter(None, [self.first_name, self.last_name])
        full = " ".join(parts)
        if full:
            return full
        if self.username:
            return f"@{self.username}"
        return str(self.sender_id)
    
    model_config = {"from_attributes": True}


class EditOut(BaseModel):
    """
    One record from the message_edits table.
    Returned as a list inside MessageDetail.
    """

    id: int
    old_text: str | None = None
    new_text: str | None = None
    edited_at: str | None = Field(None, description="ISO 8601 datetime of the edit")

    model_config = {"from_attributes": True}


# Inference values for who deleted a message.
# Implemented for two cases where it's a structural fact rather than a guess (see db/queries.py's flag_deleted()):
#   - 'channel_admin': broadcast channels restrict deletion to admins
#   - 'self': Saved Messages (chat_id == the archiving account's own Telegram user ID) — only the account owner has access to it at all
# Deliberately NOT implemented for ordinary private/group/supergroup chats — Telegram allows any party to delete a message for everyone with no time
# limit and no record of who did it, so a sender_id/timing guess there would be closer to a coin flip than a signal.
# Those always get 'unknown', which is also the column's own DEFAULT.
DeletionActorInference = Literal["channel_admin", "self", "unknown"]


class DeletionOut(BaseModel):
    """
    Deletion record for a message, embedded in MessageDetail.

    `deleted_by_inference` is:
      - 'channel_admin' for messages from a broadcast channel (only admins
        can delete channel posts)
      - 'self' for messages from Saved Messages (only the account owner has
        access to it — no ambiguity, unlike an ordinary private chat)
      - 'unknown' for every other chat type, where TeleVault deliberately
        does not attempt a guess
    This is not a partial implementation waiting to be finished for the
    'unknown' cases — it's the intended final state; a private/group guess
    was considered and rejected as unreliable.

    `inference_confidence` gives a short, fixed, human-readable note
    explaining the 'channel_admin'/'self' inference's basis. Always null
    for 'unknown' rows, since there's nothing to explain about not guessing.
    """

    id: int
    text_snapshot: str | None = Field(None, description="Copy of the message text at time of deletion")
    deleted_at: str | None = Field(None, description="ISO 8601 datetime when the deletion was detected")
    deleted_by_inference: DeletionActorInference = "unknown"
    inference_confidence: str | None = Field(
        None,
        description="Fixed explanatory note for the 'channel_admin'/'self' inference. Null for 'unknown' rows."
    )

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    """
    One row in a paginated message list.
 
    Embeds sender and chat inline to avoid N+1 lookups from the frontend.
    `chat` is None when returned from a per-chat endpoint (redundant there).
    """

    id: int = Field(..., description="Internal app's message ID.")
    tg_message_id: int = Field(..., description="Telegram's own message ID.")
    chat: ChatSummary | None = Field(None, description="Omitted on per-chat endpoints where it would be redundant")
    sender: SenderOut | None = None
    text: str | None = None
    date: str | None = Field(..., description="ISO 8601 send timestamp.")
    archived_at: str | None = Field(..., description="ISO 8601 timestamp when the app first stored this message")
    is_edited: bool = False
    edited_at: str | None = None
    is_deleted: bool = False
    deleted_at: str | None = None

    model_config = {"from_attributes": True}


class MessageDetail(BaseModel):
    """
    Full message record including edit history and deletion details. 
    Returned by GET /api/messages/{id}.
 
    Extends MessageOut so the frontend can reuse the same type for both list rows and the detail view with a simple field check.
    """

    edits: list[EditOut] = Field(
        default_factory=list,
        description="Full edit history, ordered oldest -> newest.",
    )
    deletion: DeletionOut | None = Field(None, description="Deletion record. None if the message has not been deleted")