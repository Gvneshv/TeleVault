"""
Manages the SQLite connection for the entire application.
 
It uses a single shared connection rather than opening/closing one per query.
SQLite handles this fine for a single-process app like TeleVault, and it
avoids the overhead of reconnecting on every write event.
 
WAL (Write-Ahead Logging) mode is enabled because it allows reads and writes
to happen concurrently without blocking each other - important when Telethon's
event loop is constantly firing while you might also be querying the DB manually.

Datetime handling
-----------------
Python 3.12 deprecated the built-in sqlite3 datetime adapters/converters and
they are removed in later versions. Rather than rely on them, this module
registers explicit ones that work on every Python version:
 
  - Adapter  (Python -> SQLite): datetime -> ISO 8601 TEXT string
  - Converter (SQLite -> Python): TEXT column declared DATETIME -> datetime
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level variable - holds the single connection instance.
# None until init_db() is called.
_connection: sqlite3.Connection | None = None



# ---------------------------------------------------------------------------
# Datetime adapters — registered once at import time
# ---------------------------------------------------------------------------

def _adapt_datetime(dt: datetime) -> str:
    """
    Serialize a Python datetime to an ISO 8601 string for SQLite storage.
    Timezone-aware datetimes keep their offset; naive ones are stored as-is.
    """
    return dt.isoformat()


def _convert_datetime(raw: bytes) -> datetime:
    """
    Deserialize an ISO 8601 byte string from SQLite back to a Python datetime.
    Handles both timezone-aware ('...+00:00') and naive ('...') formats.
    """
    return datetime.fromisoformat(raw.decode())


sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_converter("DATETIME", _convert_datetime)


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    """
    Open the SQLite database at the given path, apply performance settings,
    and return the connection. Also stores it internally so get_connection()
    can retrieve it later without needing the path again.
 
    Creates the database file if it doesn't exist yet.
    """
    global _connection

    # Ensure the parent directory exists (e.g. if db_path is 'data/televault.db')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Opening database at: {db_path}")

    # Pylance showed an error here ||, but it's fine
                                #  \/
    _connection = sqlite3.connect( # type: ignore
        db_path,
        # PARSE_DECLTYPES enables our registered DATETIME converter above,
        # turning TEXT columns declared as DATETIME back into Python datetimes automatically on read.
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        # check_same_thread=False is required here because Telethon runs its event loop in a separate thread from the main thread.
        # Without this flag, sqlite3 raises an error on cross-thread access.
        check_same_thread=False,
    )

    # Return rows as dict-like objects (row["column_name"] instead of row[0]).
    # Much safer and more readable than positional indexing
    _connection.row_factory = sqlite3.Row

    # WAL mode: writes go to a separate log file first, so readers are never
    # blocked by a write in progress. Better performance for our use case
    _connection.execute("PRAGMA journal_mode = WAL;")

    # Foreign key enforcement is OFF by default in SQLite - turn it on so our
    # FK constraints (chat_id, sender_id) are actually enforced.
    _connection.execute("PRAGMA foreign_keys = ON;")

    logger.info("Database connection established.")
    return _connection


def get_connection() -> sqlite3.Connection:
    """
    Return the active database connection.
    Raises an error if init_db() hasn't been called yet.
    """
    if _connection is None:
        raise RuntimeError("Database not initialised. Call init_db() before get_connection().")
    return _connection


def close_db() -> None:
    """
    Cleanly close the database connection.
    Call this on application shutdown so any buffered WAL data is flushed.
    """
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.info("Database connection closed.")