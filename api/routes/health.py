"""
GET /api/health — liveness check for the API server and its dependencies.

Used by:
    - The web UI to show a status indicator
    - Systemd / monitoring to confirm the process is alive
    - Future: heartbeat from the userbot process (Phase 3)

What this checks vs. what it doesn't:
    ✓ Database file is readable and returns rows
    ✓ Telethon .session file exists on disk
    ✗ Whether the userbot is currently connected to Telegram (that requires IPC — a Phase 3 addition, see CHANGELOG)
"""

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends

from api.dependencies import get_db
from api.schemas import HealthOut
from config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, summary="API and dependency liveness")
def health_check(db: sqlite3.Connection = Depends(get_db)) -> HealthOut:
    """
    Return liveness status for the API and its key dependencies.

    `status` is 'ok' when both checks pass, 'degraded' otherwise.
    A 200 response is always returned — the caller reads the body to determine actual health, rather than relying on HTTP status codes.
    This makes it easier to display partial-health states in the UI.
    """
    # Check 1: can we read from the database?
    try:
        from db.read_queries import get_message_count
        message_count = get_message_count(db)
        db_readable = True
    except Exception:
        db_readable = False
        message_count = 0

    # Check 2: does the Telethon session file exist?
    # Presence means the userbot has authenticated at least once.
    # Absence most likely means first-run setup hasn't completed.
    session_path = Path(settings.session_name).with_suffix(".session")
    session_exists = session_path.exists()

    status = "ok" if (db_readable and session_exists) else "degraded"

    return HealthOut(
        status=status,
        db_readable=db_readable,
        session_exists=session_exists,
        db_message_count=message_count,
    )