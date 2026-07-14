"""
Read-only query layer used exclusively by the API server.

All functions accept a sqlite3.Connection opened in read-only mode (uri=True, "file:path?mode=ro") and return plain dicts or lists of dicts - no ORM, no Pydantic here.
Pydantic validation happens in the route layer so this module stays dependency-free and easily testable.

Pagination convention throughout:
    page     : 1-based page number
    per_page : rows per page (capped at 200 in the API layer)
    Returns  : {"items": [...], "total": int}
    The caller assembles the full PaginatedResponse envelope.

All datetimes are stored as ISO 8601 strings; returned as-is.
"""

import sqlite3
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fts5_phrase_query(q: str) -> str:
    """
    Build a safe FTS5 MATCH query treating the whole input as a literal phrase,
    not as FTS5 query syntax - characters like " * - ( ) : have special meaning there (a bare hyphen is NOT, for example),
    so an unquoted user search could silently misbehave or error.
    Wrapping in quotes (escaping any literal quote in the input by doubling it, FTS5's own escaping rule) avoids that regardless of what the user types.
    """
    escaped = q.replace('"', '""')
    return f'"{escaped}"'


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    """Convert all cursor rows to dicts keyed by column name."""
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _shape_message_row(row: dict[str, Any], has_chat_columns: bool) -> dict[str, Any]:
    """
    Reshape a flat SQL row into the nested structure MessageOut/MessageDetail actually expect: {"chat": {...} | None, "sender": {...} | None, ...}.

    BUG THIS FIXES: without this step, a flat row (e.g. with a top-level "sender_id" and "chat_name" key, as produced by dict(zip(cols, row)))
    has no key literally named "chat" or "sender" at all.
    FastAPI/Pydantic validates the dict against MessageOut, finds neither key,
    and silently falls back to each field's declared default of None — for every row, always, regardless of the SQL join actually having the data.
    This was invisible in testing because Optional[None] doesn't raise a validation error; it just quietly renders as "—" in the frontend.
    Confirmed via testing that this affected 100% of rows in the Messages and Deleted views, not an occasional edge case.

    Args:
        row              : flat dict with message columns, sender_* columns, and chat_name/chat_type if has_chat_columns.
        has_chat_columns : whether this row's SELECT joined the chats table.
                           False for get_chat_messages() (chat is intentionally omitted there — see its docstring), True for get_messages() and get_message_detail().
    """
    sender = None
    if row["sender_id"] is not None:
        sender = {
            "sender_id": row["sender_id"],
            "username": row["sender_username"],
            "first_name": row["sender_first_name"],
            "last_name": row["sender_last_name"],
            # Not stored yet — Phase 3 feature, see SenderOut's docstring.
            "display_name": None,
        }

    chat = None
    if has_chat_columns:
        chat = {
            "chat_id": row["chat_id"],
            "name": row.get("chat_name"),
            "chat_type": row.get("chat_type"),
        }

    return {
        "id": row["id"],
        "tg_message_id": row["tg_message_id"],
        "chat": chat,
        "sender": sender,
        "text": row["text"],
        "date": row["date"],
        "archived_at": row["archived_at"],
        "is_edited": row["is_edited"],
        "edited_at": row["edited_at"],
        "is_deleted": row["is_deleted"],
        "deleted_at": row["deleted_at"],
    }


def _paginate(query: str, params: list, conn: sqlite3.Connection,
              page: int, per_page: int) -> dict[str, Any]:
    """
    Run a SELECT query with LIMIT/OFFSET pagination.

    Wraps the caller's query in a COUNT subquery to get the total without a second round-trip, then fetches the page.

    Args:
        query    : SQL without LIMIT/OFFSET — must be a SELECT.
        params   : Positional parameters matching the query's placeholders.
        conn     : Open read-only connection.
        page     : 1-based page number.
        per_page : Rows per page.

    Returns:
        {"items": list[dict], "total": int}
    """
    count_sql = f"SELECT COUNT(*) FROM ({query})"
    total: int = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * per_page
    paged_sql = f"{query} LIMIT ? OFFSET ?"
    cursor = conn.execute(paged_sql, params + [per_page, offset])
    items = _rows_to_dicts(cursor)

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# Chats
# ---------------------------------------------------------------------------

def get_chats(
    conn: sqlite3.Connection,
    page: int = 1,
    per_page: int = 50,
) -> dict[str, Any]:
    """
    Return all known chats sorted by most recent activity descending (i.e. the same ordering as the Telegram sidebar).

    Each row includes aggregate counts computed with subqueries so the chat list can be rendered without additional per-chat requests.

    Columns returned:
        chat_id, name, username, chat_type, first_seen, message_count, deleted_count, last_message_at, last_message_preview
    """
    sql = """
        SELECT
            c.chat_id,
            c.name,
            c.username,
            c.chat_type,
            c.first_seen,
            COUNT(m.id)                                         AS message_count,
            SUM(CASE WHEN m.is_deleted = 1 THEN 1 ELSE 0 END)   AS deleted_count,
            MAX(m.date)                                         AS last_message_at,
            -- Truncate preview to 80 chars; SUBSTR does nothing if text is NULL.
            SUBSTR(
                (SELECT m2.text
                 FROM messages m2
                 WHERE m2.chat_id = c.chat_id
                 ORDER BY m2.date DESC
                 LIMIT 1),
                1, 80
            )                                                   AS last_message_preview
        FROM chats c
        LEFT JOIN messages m ON m.chat_id = c.chat_id
        GROUP BY c.chat_id
        ORDER BY last_message_at DESC NULLS LAST
    """
    return _paginate(sql, [], conn, page, per_page)


def get_chat(conn: sqlite3.Connection, chat_id: int) -> dict[str, Any] | None:
    """
    Return a single chat record with aggregate counts.
    Returns None if the chat_id is not in the database.
    """
    sql = """
        SELECT
            c.chat_id,
            c.name,
            c.username,
            c.chat_type,
            c.first_seen,
            COUNT(m.id)                                         AS message_count,
            SUM(CASE WHEN m.is_deleted = 1 THEN 1 ELSE 0 END)   AS deleted_count,
            MAX(m.date)                                         AS last_message_at,
            SUBSTR(
                (SELECT m2.text
                 FROM messages m2
                 WHERE m2.chat_id = c.chat_id
                 ORDER BY m2.date DESC
                 LIMIT 1),
                1, 80
            )                                                   AS last_message_preview
        FROM chats c
        LEFT JOIN messages m ON m.chat_id = c.chat_id
        WHERE c.chat_id = ?
        GROUP BY c.chat_id
    """
    cursor = conn.execute(sql, [chat_id])
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def _base_message_select() -> str:
    """
    Core SELECT joining messages -> senders.
    Used by both get_messages() and get_chat_messages() to keep column lists consistent — changing the projection in one place changes both.

    Note: chat columns are NOT joined here;
    get_messages() adds them, while get_chat_messages() omits them (they're redundant per-chat).
    """
    return """
        SELECT
            m.id,
            m.tg_message_id,
            m.chat_id,
            m.text,
            m.date,
            m.archived_at,
            m.is_edited,
            m.edited_at,
            m.is_deleted,
            m.deleted_at,
            -- sender fields prefixed to avoid collision with message columns
            s.sender_id    AS sender_id,
            s.username     AS sender_username,
            s.first_name   AS sender_first_name,
            s.last_name    AS sender_last_name
        FROM messages m
        LEFT JOIN senders s ON s.sender_id = m.sender_id
    """


def get_messages(
    conn: sqlite3.Connection,
    page: int = 1,
    per_page: int = 50,
    q: str | None = None,
    chat_id: int | None = None,
    sender_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    only_deleted: bool = False,
    only_edited: bool = False,
) -> dict[str, Any]:
    """
    Global message search with optional filters.

    Used by:
        GET /api/messages          (global feed)
        GET /api/deleted           (only_deleted=True)

    Filter behaviour:
        q            : case-insensitive substring match on message text.
        chat_id      : restrict to one chat.
        sender_id    : restrict to one sender.
        date_from    : ISO 8601 string, inclusive lower bound on m.date.
        date_to      : ISO 8601 string, inclusive upper bound on m.date.
        only_deleted : if True, return only messages where is_deleted = 1.
        only_edited  : if True, return only messages where is_edited = 1.

    Also joins chat name/type for inline display (avoids a second request per row on the global feed and deleted views).
    """
    select = """
        SELECT
            m.id,
            m.tg_message_id,
            m.chat_id,
            c.name         AS chat_name,
            c.chat_type    AS chat_type,
            m.text,
            m.date,
            m.archived_at,
            m.is_edited,
            m.edited_at,
            m.is_deleted,
            m.deleted_at,
            s.sender_id    AS sender_id,
            s.username     AS sender_username,
            s.first_name   AS sender_first_name,
            s.last_name    AS sender_last_name
        FROM messages m
        LEFT JOIN senders s ON s.sender_id = m.sender_id
        LEFT JOIN chats c   ON c.chat_id   = m.chat_id
    """

    conditions: list[str] = []
    params: list[Any] = []

    if q:
        # FTS5 (trigram tokenizer) instead of LOWER_UNICODE()+LIKE - same substring-anywhere, case-insensitive-including-Cyrillic behaviour,
        # but indexed instead of a full table scan.
        # See migration 004 for why trigram specifically (matches current UX; the default FTS5 tokenizer would only match whole words, a real behaviour change).
        conditions.append("m.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)")
        params.append(_fts5_phrase_query(q))
    if chat_id is not None:
        conditions.append("m.chat_id = ?")
        params.append(chat_id)
    if sender_id is not None:
        conditions.append("m.sender_id = ?")
        params.append(sender_id)
    if date_from:
        conditions.append("m.date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("m.date <= ?")
        params.append(date_to)
    if only_deleted:
        conditions.append("m.is_deleted = 1")
    if only_edited:
        conditions.append("m.is_edited = 1")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"{select} {where} ORDER BY m.date DESC"

    result = _paginate(sql, params, conn, page, per_page)
    result["items"] = [_shape_message_row(r, has_chat_columns=True) for r in result["items"]]
    return result


def get_chat_messages(
    conn: sqlite3.Connection,
    chat_id: int,
    page: int = 1,
    per_page: int = 50,
    q: str | None = None,
    sender_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Messages within a single chat, newest first.

    Used by GET /api/chats/{chat_id}/messages.
    Chat columns are omitted (redundant in a per-chat context).
    All other filters mirror get_messages().
    """
    select = _base_message_select()

    conditions: list[str] = ["m.chat_id = ?"]
    params: list[Any] = [chat_id]

    if q:
        conditions.append("m.id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)")
        params.append(_fts5_phrase_query(q))
    if sender_id is not None:
        conditions.append("m.sender_id = ?")
        params.append(sender_id)
    if date_from:
        conditions.append("m.date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("m.date <= ?")
        params.append(date_to)

    where = "WHERE " + " AND ".join(conditions)
    sql = f"{select} {where} ORDER BY m.date DESC"

    result = _paginate(sql, params, conn, page, per_page)
    result["items"] = [_shape_message_row(r, has_chat_columns=False) for r in result["items"]]
    return result


def get_message_detail(
    conn: sqlite3.Connection,
    message_id: int,
) -> dict[str, Any] | None:
    """
    Single message with full edit history and deletion record.
    Used by GET /api/messages/{id}.

    Returns None if message_id does not exist.

    Edits are attached as a list under the key 'edits'.
    Deletion record (if any) is attached under the key 'deletion'.
    """
    # Base message row.
    # Previously used _base_message_select() (sender-only, no chats join)
    # — added the chats join explicitly here since this endpoint's response (MessageDetail) includes a chat field same as MessageOut,
    # and there was no documented reason to omit it the way get_chat_messages() intentionally does.
    select = """
        SELECT
            m.id,
            m.tg_message_id,
            m.chat_id,
            c.name         AS chat_name,
            c.chat_type    AS chat_type,
            m.text,
            m.date,
            m.archived_at,
            m.is_edited,
            m.edited_at,
            m.is_deleted,
            m.deleted_at,
            s.sender_id    AS sender_id,
            s.username     AS sender_username,
            s.first_name   AS sender_first_name,
            s.last_name    AS sender_last_name
        FROM messages m
        LEFT JOIN senders s ON s.sender_id = m.sender_id
        LEFT JOIN chats c   ON c.chat_id   = m.chat_id
    """
    cursor = conn.execute(f"{select} WHERE m.id = ?", [message_id])
    row = cursor.fetchone()
    if row is None:
        return None

    cols = [col[0] for col in cursor.description]
    flat = dict(zip(cols, row))
    result = _shape_message_row(flat, has_chat_columns=True)

    # Edit history — oldest first so the UI can render a timeline
    edits_cursor = conn.execute(
        """
        SELECT id, old_text, new_text, edited_at
        FROM message_edits
        WHERE message_id = ?
        ORDER BY edited_at ASC
        """,
        [message_id],
    )
    result["edits"] = _rows_to_dicts(edits_cursor)

    # Deletion record with actor inference
    del_cursor = conn.execute(
        """
        SELECT id, text_snapshot, deleted_at, deleted_by_inference, inference_confidence
        FROM message_deletions
        WHERE message_id = ?
        LIMIT 1
        """,
        [message_id],
    )
    del_row = del_cursor.fetchone()
    if del_row:
        del_cols = [col[0] for col in del_cursor.description]
        result["deletion"] = dict(zip(del_cols, del_row))
    else:
        result["deletion"] = None

    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Aggregate statistics for the /api/stats endpoint.

    Runs three queries:
        1. Global totals (counts, archiving_since).
        2. Per-chat breakdown sorted by message volume descending.

    These are intentionally separate queries rather than one large JOIN so SQLite's query planner handles each simply.
    Stats are not latency-critical — they're for a dashboard, not a hot path.
    """
    totals_row = conn.execute(
        """
        SELECT
            COUNT(*)                                           AS total_messages,
            SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END)  AS total_deleted,
            SUM(CASE WHEN is_edited  = 1 THEN 1 ELSE 0 END)  AS total_edited,
            MIN(archived_at)                                   AS archiving_since
        FROM messages
        """
    ).fetchone()

    total_chats = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
    total_senders = conn.execute("SELECT COUNT(*) FROM senders").fetchone()[0]

    per_chat_cursor = conn.execute(
        """
        SELECT
            c.chat_id,
            c.name,
            c.chat_type,
            COUNT(m.id)                                        AS message_count,
            SUM(CASE WHEN m.is_deleted = 1 THEN 1 ELSE 0 END) AS deleted_count,
            SUM(CASE WHEN m.is_edited  = 1 THEN 1 ELSE 0 END) AS edited_count,
            MIN(m.date)                                        AS first_message_at,
            MAX(m.date)                                        AS last_message_at
        FROM chats c
        LEFT JOIN messages m ON m.chat_id = c.chat_id
        GROUP BY c.chat_id
        ORDER BY message_count DESC
        """
    )
    per_chat = _rows_to_dicts(per_chat_cursor)

    return {
        "total_messages": totals_row[0] or 0,
        "total_deleted": totals_row[1] or 0,
        "total_edited": totals_row[2] or 0,
        "total_chats": total_chats,
        "total_senders": total_senders,
        "archiving_since": totals_row[3],
        "per_chat": per_chat,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def get_message_count(conn: sqlite3.Connection) -> int:
    """
    Quick sanity check used by the health endpoint.
    Returns total row count from the messages table.
    """
    return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]