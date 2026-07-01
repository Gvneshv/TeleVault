"""
GET /api/deleted — paginated list of all deleted messages across all chats.

This is intentionally a thin wrapper around GET /api/messages with only_deleted=True.
It exists as its own endpoint because:

    1. It's a primary UI view (the "Deleted" tab) and deserves a clean URL.
    2. It may grow its own filters in Phase 3 (e.g. filter by inference actor, filter by chat, date range) without affecting the general /messages API.
"""

import sqlite3
from math import ceil

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_db
from api.schemas import MessageOut, PaginatedResponse
from db.read_queries import get_messages

router = APIRouter(tags=["deleted"])


@router.get(
    "/deleted",
    response_model=PaginatedResponse[MessageOut],
    summary="List all deleted messages across all chats",
)
def list_deleted(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Substring search within message text."),
    chat_id: int | None = Query(None, description="Restrict to one chat."),
    sender_id: int | None = Query(None, description="Restrict to one sender."),
    date_from: str | None = Query(
        None, description="ISO 8601 lower bound on the original message date."
    ),
    date_to: str | None = Query(
        None, description="ISO 8601 upper bound on the original message date."
    ),
    db: sqlite3.Connection = Depends(get_db),
) -> PaginatedResponse[MessageOut]:
    """
    Return all messages that have been flagged as deleted, newest first.

    Results include chat and sender info inline. The `deleted_at` field on each row indicates when TeleVault detected the deletion.

    For the full deletion record (actor inference, text snapshot), fetch GET /api/messages/{id} which returns a MessageDetail with the `deletion` sub-object attached.
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
        only_deleted=True,
    )
    total = result["total"]
    return {
        "items": result["items"],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, ceil(total / per_page)),
    }