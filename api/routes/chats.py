"""
Chat-related endpoints:

    GET /api/chats                      — paginated list of all known chats
    GET /api/chats/{chat_id}            — single chat with aggregate counts
    GET /api/chats/{chat_id}/messages   — paginated messages within one chat
"""

import sqlite3
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db
from api.schemas import ChatOut, MessageOut, PaginatedResponse
from db.read_queries import get_chat, get_chats, get_chat_messages

router = APIRouter(tags=["chats"])


def _build_page(result: dict, page: int, per_page: int) -> dict:
    """Attach pagination metadata to a raw _paginate() result."""
    total = result["total"]
    return {
        "items": result["items"],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, ceil(total / per_page)),
    }


@router.get(
    "/chats",
    response_model=PaginatedResponse[ChatOut],
    summary="List all archived chats",
)
def list_chats(
    page: int = Query(1, ge=1, description="Page number (1-based)."),
    per_page: int = Query(50, ge=1, le=200, description="Results per page."),
    db: sqlite3.Connection = Depends(get_db),
) -> PaginatedResponse[ChatOut]:
    """
    Return all chats TeleVault has seen, sorted by most recent message (same ordering as the Telegram sidebar).

    Each chat includes aggregate counts (total messages, deleted messages) and a preview of the most recent message text, so the sidebar can be rendered without additional per-chat requests.
    """
    result = get_chats(db, page=page, per_page=per_page)
    return _build_page(result, page, per_page)


@router.get(
    "/chats/{chat_id}",
    response_model=ChatOut,
    summary="Get a single chat by ID",
)
def get_chat_by_id(
    chat_id: int,
    db: sqlite3.Connection = Depends(get_db),
) -> ChatOut:
    """
    Return a single chat record with aggregate counts.
    Raises 404 if the chat_id is not in the archive.
    """
    row = get_chat(db, chat_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found.")
    return row


@router.get(
    "/chats/{chat_id}/messages",
    response_model=PaginatedResponse[MessageOut],
    summary="List messages in a chat",
)
def list_chat_messages(
    chat_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Substring search within message text."),
    sender_id: int | None = Query(None, description="Filter by sender ID."),
    date_from: str | None = Query(None, description="ISO 8601 lower bound on message date."),
    date_to: str | None = Query(None, description="ISO 8601 upper bound on message date."),
    db: sqlite3.Connection = Depends(get_db),
) -> PaginatedResponse[MessageOut]:
    """
    Return messages within a single chat, newest first.

    The `chat` field is omitted from each MessageOut row here — it would be redundant since all messages belong to the same chat_id.

    Supports text search and date range filtering via query parameters.
    """
    # Confirm the chat exists before querying messages.
    if get_chat(db, chat_id) is None:
        raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found.")

    result = get_chat_messages(
        db,
        chat_id=chat_id,
        page=page,
        per_page=per_page,
        q=q,
        sender_id=sender_id,
        date_from=date_from,
        date_to=date_to,
    )
    return _build_page(result, page, per_page)