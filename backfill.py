"""
One-off / on-demand script to archive historical messages - the ones sent before TeleVault was running, or before a chat was ever seen by it.

Run with:
    python backfill.py                      # every chat you're in
    python backfill.py --chat @someusername  # one chat only
    python backfill.py --chat -1001234567890 # one chat by numeric ID
    python backfill.py --chat @someusername --limit 500  # cap per chat, useful for testing

Important limitations - Telegram's API, not something TeleVault can work around:
  - Deleted messages cannot be backfilled.
    Telegram's history API only returns messages that currently exist in a chat.
    If a message was deleted before TeleVault started archiving that chat, that history is gone - there is no way to recover it.
  - Edit history cannot be backfilled either.
    Only the CURRENT (latest) text of each historical message is available,
    so backfilled messages are stored as not-yet-edited (is_edited=0) even if they actually were edited before backfill ran.
    There's no way to see prior versions of a message you didn't already have archived.

Do not run this at the same time as main.py (the live userbot) against the same .session file - Telethon sessions support one active connection at a time.
Stop main.py first, run this, then start main.py again.

Idempotent: insert_message() uses INSERT OR IGNORE (see db/queries.py), so running this more than once,
or interrupting it partway through and re-running later, is always safe - already-archived messages are silently skipped, never duplicated.
"""

import argparse
import asyncio
import logging
import json
import signal
import sqlite3
import time

from pathlib import Path

from datetime import datetime

from telethon import TelegramClient, functions, utils
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerChat

import db
from config import settings
from utils.logging_setup import setup_logging
from handlers.helpers import get_chat_type, get_sender_fields, resolve_message_text

logger = logging.getLogger(__name__)

# Log a progress line every this many messages processed within a single chat - large channels/years of history can take a long time,
# and a completely silent script for that long looks hung even when it isn't.
PROGRESS_INTERVAL = 500

# If False, STATUS_PATH is ignored and status is printed to stderr instead.
STATUS_PATH = Path(settings.backfill_status_path) if False else None  # set properly below via settings import already present


def _write_status(data: dict) -> None:
    """
    Overwrite the backfill status file.
    Read by GET /api/backfill/status so the web UI can render progress without any direct coupling to this process beyond this one file.
    Temp-file-then-replace so the API never reads a half-written file.
    """
    path = Path(settings.backfill_status_path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


_cancelled = False


def _handle_sigterm(signum, frame) -> None:
    """
    Flip a flag rather than raising immediately - lets the current message finish and insert_message() own commit land cleanly before the run loop notices and exits,
    so a Cancel click doesn't look like a crash in backfill_runs.
    """
    global _cancelled
    _cancelled = True
    logger.info("Cancellation requested - finishing the current message, then stopping.")


async def backfill_chat(client: TelegramClient, conn, chat, limit: int | None, status_cb=None) -> tuple[int, int]:
    """
    Archive all currently-existing history for one chat.

    Returns (stored, skipped).
    skipped covers both "already archived" (INSERT OR IGNORE no-op) and "nothing worth archiving" (media, stickers, unsupported service messages)
    - not distinguished further, since this is just a progress summary, not an audit log.
    """
    chat_type = get_chat_type(chat)
    chat_name = getattr(chat, "title", None) or getattr(chat, "first_name", None)
    chat_username = (getattr(chat, "username", None) or "").lstrip("@") or None

    # Detect a completed group->supergroup migration before archiving history, so any messages stored below go under the canonical (new) chat_id,
    # and any pre-existing basic-group rows get picked up by merge_migrated_chats.py instead of staying orphaned.
    if chat_type in ("supergroup", "channel"):
        try:
            full = await client(functions.channels.GetFullChannelRequest(chat))
            migrated_from = getattr(full.full_chat, "migrated_from_chat_id", None)
            if migrated_from:
                old_chat_id = utils.get_peer_id(PeerChat(migrated_from))
                db.queries.record_chat_migration(conn, old_chat_id=old_chat_id, new_chat_id=chat.id)
        except Exception:
            logger.exception(f"Could not check migration status for '{chat_name}' - continuing without it.")

    db.queries.upsert_chat(
        conn,
        chat_id=utils.get_peer_id(chat),
        name=chat_name,
        chat_type=chat_type,
        username=chat_username,
    )

    stored = 0
    skipped = 0
    processed = 0

    # reverse=True walks oldest -> newest.
    # Doesn't affect correctness here (INSERT OR IGNORE makes this safe to interrupt and resume any time),
    # just makes archived_at ordering read naturally if you ever look at the raw table.
    async for message in client.iter_messages(chat, reverse=True, limit=limit):
        if _cancelled:
            logger.info(f"Cancelled mid-chat at '{chat_name}' ({processed} processed).")
            break

        processed += 1
        if processed % PROGRESS_INTERVAL == 0:
            logger.info(f"  ...{processed} messages processed so far ({stored} stored).")
            if status_cb:
                status_cb(processed)

        text = resolve_message_text(message)
        if not text:
            skipped += 1
            continue

        if message.sender_id is not None:
            sender = await message.get_sender()
            username, first_name, last_name = get_sender_fields(sender)
            # commit=False: grouped with insert_message()'s own commit below,
            # same rationale as handlers/on_message.py - avoids a SQLite WAL snapshot-isolation issue where the FK check in insert_message
            # can't see a separately-committed parent row.
            # See upsert_sender's docstring in db/queries.py.
            db.queries.upsert_sender(
                conn,
                sender_id=message.sender_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                commit=False,
            )

        row_id = db.queries.insert_message(
            conn,
            tg_message_id=message.id,
            chat_id=utils.get_peer_id(chat),
            sender_id=message.sender_id,
            text=text,
            date=message.date,
        )
        if row_id is not None:
            stored += 1
        else:
            skipped += 1

    return stored, skipped


async def run(chat_selector: str | None, limit: int | None) -> None:
    setup_logging(log_level=settings.log_level, log_file=settings.log_file)

    conn = db.init_db(settings.db_path)
    db.apply_schema(conn)

    run_conn = sqlite3.connect(settings.db_path)
    run_id = run_conn.execute(
        "INSERT INTO backfill_runs (status, chat_selector) VALUES ('running', ?)",
        (chat_selector,),
    ).lastrowid
    run_conn.commit()

    signal.signal(signal.SIGTERM, _handle_sigterm)

    status = {
        "state": "running",
        "started_at": datetime.utcnow().isoformat(),
        "chats_total": None,
        "chats_done": 0,
        "current_chat": None,
        "overall_processed": 0,
        "overall_total": 0,
    }
    _write_status(status)

    client = TelegramClient(settings.session_name, settings.api_id, settings.api_hash)
    await client.start(phone=settings.phone)

    me = await client.get_me()
    logger.info(f"Authenticated as: {me.first_name} (id={me.id})")

    if chat_selector:
        # Numeric chat_id or @username/invite-style identifier - get_entity() resolves either.
        try:
            target = int(chat_selector)
        except ValueError:
            target = chat_selector
        chats = [await client.get_entity(target)]
    else:
        logger.warning(
            "No --chat given - backfilling EVERY chat you're in." \
            "This can take a long time and make many API requests for accounts with "
            "years of history or large channels. Press Ctrl-C to abort."
        )
        chats = [dialog.entity async for dialog in client.iter_dialogs()]

    total_stored = 0
    total_skipped = 0

    status["chats_total"] = len(chats)
    for chat in chats:
        try:
            total_msg = await client.get_messages(chat, limit=1)
            status["overall_total"] += total_msg.total or 0
        except Exception:
            pass  # best-effort estimate only
    _write_status(status)

    for chat in chats:
        name = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(chat.id)
        logger.info(f"Backfilling '{name}'...")

        stored = skipped = 0
        max_flood_retries = 5
        failed = False
        for attempt in range(1, max_flood_retries + 1):
            try:
                status["current_chat"] = name
                base_processed = status["overall_processed"]

                def _status_cb(processed_in_chat, base=base_processed):
                    status["overall_processed"] = base + processed_in_chat
                    _write_status(status)

                stored, skipped = await backfill_chat(client, conn, chat, limit)
                break
            except FloodWaitError as e:
                # Expected, not a bug: Telegram's own rate limit.
                # Telethon already auto-waits for short flood waits internally (below its flood_sleep_threshold);
                # this only fires for longer ones.
                # Logged plainly (no traceback - this isn't an error, it's Telegram asking us to slow down) and retried.
                # Retrying re-walks this chat's history from the start rather than resuming from where it stopped - wasteful on API calls for a chat that floods repeatedly, but simpler and safer than resuming mid-iterator, and INSERT OR IGNORE means no duplicate rows either way.
                logger.warning(
                    f"Rate limited by Telegram while backfilling '{name}' "
                    f"(attempt {attempt}/{max_flood_retries}) - waiting "
                    f"{e.seconds}s before retrying. This is normal for "
                    f"large histories, not an error."
                )
                await asyncio.sleep(e.seconds + 1)
            except Exception:
                # One chat failing for a genuinely unexpected reason (permissions, a weird entity type, etc.) shouldn't stop the rest of the run.
                logger.exception(f"Failed to backfill '{name}' - skipping to the next chat.")
                failed = True
                break
        else:
            logger.error(
                f"Gave up on '{name}' after {max_flood_retries} flood-wait "
                f"retries - Telegram kept rate limiting this chat. Try "
                f"again later, perhaps with --chat '{name}' on its own."
            )
            continue

        if failed:
            continue

        logger.info(f"  '{name}': {stored} stored, {skipped} skipped.")
        total_stored += stored
        total_skipped += skipped

    logger.info(f"Backfill complete: {total_stored} stored, {total_skipped} skipped overall.")

    final_status = "cancelled" if _cancelled else "error" if total_stored == 0 and total_skipped == 0 and _process_failed else "completed"
    status["state"] = final_status
    _write_status(status)
    run_conn.execute(
        "UPDATE backfill_runs SET finished_at = CURRENT_TIMESTAMP, status = ?, "
        "messages_stored = ?, messages_skipped = ? WHERE id = ?",
        (final_status, total_stored, total_skipped, run_id),
    )
    run_conn.commit()
    run_conn.close()

    await client.disconnect()
    db.close_db()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Archive historical messages sent before TeleVault was running."
    )
    parser.add_argument(
        "--chat",
        metavar="ID_OR_USERNAME",
        default=None,
        help="Backfill only this chat (numeric chat ID or @username). Omit to backfill every chat you're in.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of messages fetched per chat. Omit for full history. Useful for a quick test run.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.chat, args.limit))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()