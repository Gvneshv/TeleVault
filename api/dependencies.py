"""
FastAPI dependencies shared across route modules.

Currently provides a single dependency: get_db(), which yields a read-only SQLite connection for the duration of one request and closes it in the finally block — whether the request succeeds or raises an exception.

Why read-only URI mode?
    Opening the SQLite file with "file:path?mode=ro" means SQLite will hard-error if any code accidentally attempts a write.
    This is the right safeguard given that the userbot and API share the same file: writes from both sides simultaneously, even if rare, can corrupt WAL state.

Why a new connection per request rather than a pool?
    SQLite connections are cheap.
    A connection pool adds complexity without benefit at this scale (single user, personal tool).
    If this changes when migrating to PostgreSQL in Phase 4, this is the only file that needs updating — all route code uses the `db: Connection` parameter unchanged.
"""

import sqlite3
from pathlib import Path
from typing import Generator

from fastapi import HTTPException

from config import settings


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Yield a read-only SQLite connection for one request, then close it.

    Usage in a route:
        from fastapi import Depends
        from api.dependencies import get_db

        @router.get("/example")
        def example(db: sqlite3.Connection = Depends(get_db)):
            ...

    Raises:
        HTTPException 503 if the database file cannot be opened (e.g. the file doesn't exist yet because the userbot has never run).
    """
    db_path = Path(settings.db_path).resolve()

    # SQLite URI mode: mode=ro refuses writes at the driver level.
    uri = f"file:{db_path}?mode=ro"

    try:
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        # Return rows as sqlite3.Row so columns are accessible by name, though _rows_to_dicts() in read_queries.py converts them to plain dicts before they reach here.
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Database unavailable: {exc}. "
                "Ensure the TeleVault userbot has run at least once."
            ),
        ) from exc

    try:
        yield conn
    finally:
        conn.close()