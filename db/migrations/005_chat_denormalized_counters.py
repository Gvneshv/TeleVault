"""
Denormalizes per-chat aggregates onto the chats table itself:
    message_count, deleted_count, edited_count, first_message_at, last_message_at, last_message_preview

...maintained incrementally by triggers on the messages table, rather than computed from scratch on every read.

Why: GET /api/chats and GET /api/stats previously computed these via a LEFT JOIN + GROUP BY across the ENTIRE messages table on every single request
(see the old get_chats()/get_stats() in db/read_queries.py) - correct, but its cost scales with total archive size, not with what's actually displayed on the page.
At real scale (~460k messages, see schema.py's changelog) this got slow enough that the UI looked hung.
Denormalized columns turn both into a plain SELECT over the small chats table - cost stays flat as the archive keeps growing.

Triggers, not call-site changes in db/queries.py:
Chosen over updating insert_message()/flag_deleted()/record_edit() at their call sites,
because triggers guarantee every write path stays in sync automatically - including merge_chat()'s raw bulk UPDATE/DELETE statements,
which don't go through those per-message helper functions at all and would be easy to miss
(and easy to silently drift out of sync later) if the counters were maintained by hand in Python instead.
This mirrors the existing precedent in 004_fts5_search.py, which keeps messages_fts in sync via triggers rather than editing every write call site.

Known limitation, accepted deliberately:
first_message_at / last_message_at / last_message_preview are NOT recomputed on DELETE.
A real row delete from `messages` only happens in merge_chat()'s duplicate-cleanup path
(a rare, one-off admin operation - see its docstring, which already flags cases needing "manual review"),
and even then only for rows that failed to move (already superseded by a surviving row under the destination chat_id).
Recomputing the correct new min/max after a delete would require a full rescan of that chat's messages, which defeats the point of denormalizing.
message_count/deleted_count/edited_count *are* kept exactly correct on delete, since those are simple decrements, not extrema.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)

_NEW_COLUMNS = {
    "message_count": "INTEGER NOT NULL DEFAULT 0",
    "deleted_count": "INTEGER NOT NULL DEFAULT 0",
    "edited_count": "INTEGER NOT NULL DEFAULT 0",
    "first_message_at": "DATETIME",
    "last_message_at": "DATETIME",
    "last_message_preview": "TEXT",
}

# Each trigger body only needs a plain UPDATE ... WHERE chat_id = ? - no separate SELECT-then-UPDATE round trip,
# since MAX()/MIN() as 2+-argument scalar functions (not the 1-argument aggregate form) let the new extremum be computed inline against the column's current value.
_TRIGGERS = [
    # New message: bump message_count/edited_count/deleted_count for its chat,
    # and extend first_message_at/last_message_at (+ preview) if this message is now the earliest/latest seen for that chat.
    """
    CREATE TRIGGER IF NOT EXISTS chats_counters_ai AFTER INSERT ON messages BEGIN
        UPDATE chats SET
            message_count = message_count + 1,
            deleted_count = deleted_count + new.is_deleted,
            edited_count = edited_count + new.is_edited,
            first_message_at = MIN(COALESCE(first_message_at, new.date), new.date),
            last_message_at = MAX(COALESCE(last_message_at, new.date), new.date),
            last_message_preview = CASE
                WHEN new.date >= COALESCE(last_message_at, new.date)
                THEN SUBSTR(new.text, 1, 80)
                ELSE last_message_preview
            END
        WHERE chat_id = new.chat_id;
    END
    """,
    # A message is flagged deleted after the fact (flag_deleted()'s UPDATE) - adjust deleted_count by the difference
    # (handles an eventual un-flag too, though nothing does that today).
    """
    CREATE TRIGGER IF NOT EXISTS chats_counters_au_deleted
    AFTER UPDATE OF is_deleted ON messages
    WHEN new.is_deleted != old.is_deleted
    BEGIN
        UPDATE chats SET deleted_count = deleted_count + (new.is_deleted - old.is_deleted)
        WHERE chat_id = new.chat_id;
    END
    """,
    # A message is edited (record_edit()'s UPDATE) - same idea for edited_count.
    """
    CREATE TRIGGER IF NOT EXISTS chats_counters_au_edited
    AFTER UPDATE OF is_edited ON messages
    WHEN new.is_edited != old.is_edited
    BEGIN
        UPDATE chats SET edited_count = edited_count + (new.is_edited - old.is_edited)
        WHERE chat_id = new.chat_id;
    END
    """,
    # A message moves to a different chat_id (merge_chat()'s bulk migration UPDATE, for basic-group -> supergroup upgrades)
    # - move its contribution from the old chat's counters to the new chat's.
    """
    CREATE TRIGGER IF NOT EXISTS chats_counters_au_chatid
    AFTER UPDATE OF chat_id ON messages
    WHEN new.chat_id != old.chat_id
    BEGIN
        UPDATE chats SET
            message_count = message_count - 1,
            deleted_count = deleted_count - old.is_deleted,
            edited_count = edited_count - old.is_edited
        WHERE chat_id = old.chat_id;

        UPDATE chats SET
            message_count = message_count + 1,
            deleted_count = deleted_count + new.is_deleted,
            edited_count = edited_count + new.is_edited,
            first_message_at = MIN(COALESCE(first_message_at, new.date), new.date),
            last_message_at = MAX(COALESCE(last_message_at, new.date), new.date),
            last_message_preview = CASE
                WHEN new.date >= COALESCE(last_message_at, new.date)
                THEN SUBSTR(new.text, 1, 80)
                ELSE last_message_preview
            END
        WHERE chat_id = new.chat_id;
    END
    """,
    # A message row is deleted outright - only happens in merge_chat()'s duplicate-cleanup path today
    # (see this module's docstring for why first/last_message_at aren't corrected here).
    """
    CREATE TRIGGER IF NOT EXISTS chats_counters_ad AFTER DELETE ON messages BEGIN
        UPDATE chats SET
            message_count = message_count - 1,
            deleted_count = deleted_count - old.is_deleted,
            edited_count = edited_count - old.is_edited
        WHERE chat_id = old.chat_id;
    END
    """,
    # A message's text changes (record_edit()'s UPDATE) - if this happens to be the chat's current latest message, its stale preview needs refreshing too.
    # Matched by date rather than message id: exactly the message currently reflected in last_message_at is the one whose edit should update last_message_preview.
    """
    CREATE TRIGGER IF NOT EXISTS chats_counters_au_text
    AFTER UPDATE OF text ON messages
    WHEN new.text IS NOT old.text
    BEGIN
        UPDATE chats SET last_message_preview = SUBSTR(new.text, 1, 80)
        WHERE chat_id = new.chat_id AND last_message_at = new.date;
    END
    """,
]

# One-time pass to populate the new columns for chats that already have messages archived.
# The triggers above only cover writes from here on.
# Mirrors exactly what the old get_chats()/get_stats() computed live.
_BACKFILL_SQL = """
UPDATE chats SET
    message_count = (SELECT COUNT(*) FROM messages WHERE messages.chat_id = chats.chat_id),
    deleted_count = (SELECT COUNT(*) FROM messages WHERE messages.chat_id = chats.chat_id AND is_deleted = 1),
    edited_count = (SELECT COUNT(*) FROM messages WHERE messages.chat_id = chats.chat_id AND is_edited = 1),
    first_message_at = (SELECT MIN(date) FROM messages WHERE messages.chat_id = chats.chat_id),
    last_message_at = (SELECT MAX(date) FROM messages WHERE messages.chat_id = chats.chat_id),
    last_message_preview = (
        SELECT SUBSTR(text, 1, 80) FROM messages
        WHERE messages.chat_id = chats.chat_id
        ORDER BY date DESC LIMIT 1
    )
"""

# chats is small (hundreds/thousands of rows, not hundreds of thousands), so this index is more "cheap insurance" than a load-bearing necessity.
_INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_chats_last_message_at ON chats(last_message_at DESC)"


def run(conn: sqlite3.Connection) -> None:
    """
    Apply migration 005: add the counter columns to chats, create the triggers that keep them in sync going forward,
    then do a one-time backfill pass over whatever's already archived.

    Idempotency: checked via PRAGMA table_info rather than a version table - if the columns are already there, this entire migration is a no-op
    (triggers use IF NOT EXISTS too, but there's no need to even reach them).
    """
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(chats)")}
    missing_columns = {
        name: ddl for name, ddl in _NEW_COLUMNS.items() if name not in existing_columns
    }

    if not missing_columns:
        logger.debug("Migration 005: chats counter columns already present, skipped.")
        return

    try:
        for name, ddl in missing_columns.items():
            conn.execute(f"ALTER TABLE chats ADD COLUMN {name} {ddl}")
        conn.commit()

        for trigger_sql in _TRIGGERS:
            conn.execute(trigger_sql)
        conn.execute(_INDEX_SQL)
        conn.commit()

        conn.execute(_BACKFILL_SQL)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    logger.info(
        "Migration 005 applied: chats counter columns added, sync triggers created, existing rows backfilled."
    )
