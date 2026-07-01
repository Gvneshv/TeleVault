"""
Global message endpoints:

    GET /api/messages           — global message feed with filters
    GET /api/messages/{id}      — single message with edit history + deletion
"""

import sqlite3
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db
from api.schemas import MessageDetail, MessageOut, PaginatedResponse
from db.read_queries import get_message_detail, get_messages

router = APIRouter(tags=["messages"])


@router.get(
    "/messages",
    response_model=PaginatedResponse[MessageOut],
    summary="Global message feed with optional filters",
)
def list_messages(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Substring search within message text."),
    chat_id: int | None = Query(None, description="Restrict to one chat."),
    sender_id: int | None = Query(None, description="Restrict to one sender."),
    date_from: str | None = Query(
        None, description="ISO 8601 inclusive lower bound on message date."
    ),
    date_to: str | None = Query(
        None, description="ISO 8601 inclusive upper bound on message date."
    ),
    only_edited: bool = Query(False, description="Return only edited messages."),
    db: sqlite3.Connection = Depends(get_db),
) -> PaginatedResponse[MessageOut]:
    """
    Return all archived messages across all chats, newest first.

    Each row embeds sender and chat info inline so the frontend doesn't need additional requests per row.

    Tip: combine `q` with `chat_id` or `sender_id` to narrow searches.
    Date bounds accept any ISO 8601 string — full datetime or date-only ('2025-01-15') both work since SQLite compares them lexicographically.
    """
    result = get_messages(
        db,
        page=page,
        per_page=per_page,
        q=q,
        chat_id=chat_id,
        sender_id=sender_id,
        date_from=date_from,
        date_to=date_to,
        only_edited=only_edited,
        only_deleted=False,
    )
    total = result["total"]
    return {
        "items": result["items"],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, ceil(total / per_page)),
    }


@router.get(
    "/messages/{message_id}",
    response_model=MessageDetail,
    summary="Get a single message with edit history and deletion record",
)
def get_message(
    message_id: int,
    db: sqlite3.Connection = Depends(get_db),
) -> MessageDetail:
    """
    Return a single archived message by its internal TeleVault ID (not the Telegram message ID, which is only unique within a chat).

    The response extends MessageOut with:
      - `edits`    : full edit history, oldest → newest
      - `deletion` : deletion record with actor inference, or null
    """
    row = get_message_detail(db, message_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Message {message_id} not found."
        )
    return row