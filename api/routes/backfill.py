"""
Endpoints for triggering, monitoring, and reviewing backfill runs from the web UI.

backfill.py always runs as its OWN subprocess with its own TelegramClient - never imported into this process - so a crash/hang there never affects the API server,
and the API never needs its own Telegram session.
Progress is shared only via backfill_status_path (JSON) and the backfill_runs table - no in-process coupling.
"""
import json
import signal
import subprocess
import sys
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from config import settings

from api.dependencies import get_db

router = APIRouter(prefix="/api/backfill", tags=["backfill"])
STALE_AFTER_SECONDS = 60
_process: subprocess.Popen | None = None


class BackfillStartRequest(BaseModel):
    chat: str | None = None
    limit: int | None = None


def _telethon_is_running() -> bool:
    path = Path(settings.heartbeat_path)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        return (time.time() - data["updated_at"]) < STALE_AFTER_SECONDS
    except Exception:
        return False


@router.post("/start")
def start_backfill(body: BackfillStartRequest):
    global _process
    if _process is not None and _process.poll() is None:
        raise HTTPException(409, "A backfill is already running.")
    if _telethon_is_running():
        raise HTTPException(
            409,
            "The live userbot (main.py) appears to be connected. Stop it before "
            "starting a backfill - Telethon sessions only support one active "
            "connection at a time.",
        )
    cmd = [sys.executable, "backfill.py"]
    if body.chat:
        cmd += ["--chat", body.chat]
    if body.limit:
        cmd += ["--limit", str(body.limit)]
    _process = subprocess.Popen(cmd)
    return {"started": True, "pid": _process.pid}


@router.post("/cancel")
def cancel_backfill():
    global _process
    if _process is None or _process.poll() is not None:
        raise HTTPException(409, "No backfill is currently running.")
    _process.send_signal(signal.SIGTERM)
    return {"cancelling": True}


@router.get("/status")
def get_backfill_status():
    path = Path(settings.backfill_status_path)
    if not path.exists():
        return {"state": "idle"}
    return json.loads(path.read_text())


@router.get("/history")
def get_backfill_history(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT id, started_at, finished_at, status, chats_total, chats_done, "
        "messages_stored, messages_skipped, error_message FROM backfill_runs "
        "ORDER BY started_at DESC LIMIT 50"
    ).fetchall()
    return [dict(row) for row in rows]