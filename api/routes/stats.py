"""
GET /api/stats — global archive statistics for the dashboard view.
"""

import sqlite3

from fastapi import APIRouter, Depends

from api.dependencies import get_db
from api.schemas import StatsOut
from db.read_queries import get_stats

router = APIRouter(tags=["stats"])


@router.get(
    "/stats",
    response_model=StatsOut,
    summary="Global archive statistics",
)
def archive_stats(db: sqlite3.Connection = Depends(get_db)) -> StatsOut:
    """
    Return aggregate statistics for the dashboard:

    - Global totals: messages, deleted, edited, chats, senders
    - `archiving_since`: datetime of the earliest archived message
    - `per_chat`: per-chat breakdown sorted by message volume descending

    Percentages (e.g. "X% of messages were deleted") are intentionally omitted from the response — the frontend computes them from the raw counts to avoid float precision noise in the API.
    """
    return get_stats(db)