"""
Shared building blocks used across multiple response schemas
"""

from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic pagination envelope returned by all list endpoints.
 
    Example response shape:
        {
            "items": [...],
            "total": 1024,
            "page": 2,
            "per_page": 50,
            "pages": 21
        }
 
    The frontend uses `total` and `pages` to render pagination controls
    without needing a separate count request.
    """

    items: list[T]
    total: int = Field(..., description="Total number of matching records.")
    page: int = Field(..., ge=1, description="Current page number.")
    per_page: int = Field(..., ge=1, le=200, description="Records per page.")
    pages: int = Field(..., description="Total number of pages.")


class HealthOut(BaseModel):
    """
    Liveness response from GET /api/health.
 
    `db_readable` confirms the SQLite file is accessible and returns rows.
    `session_exists` confirms the Telethon .session file is present on disk
    (it does NOT mean the userbot is currently connected - that would require IPC, which is out of scope for Phase 2).
    """

    status: str = Field(..., description="'ok' or 'degraded'.")
    db_readable: bool
    session_exists: bool
    db_message_count: int = Field(..., description="Quick sanity check - total rows in messages table.")