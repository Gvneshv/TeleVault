"""
FastAPI application factory and lifespan manager for the TeleVault API.

Process topology reminder:
    The userbot (main.py) and this API server are two separate processes sharing one SQLite file.
    The userbot writes; this server only reads.
    Never open a write connection here — use db.get_read_connection() from api/dependencies.py exclusively.

Running in development:
    uvicorn televault.api.server:app --reload --port 8000

On VPS (via systemd):
    ExecStart=uvicorn televault.api.server:app --host 127.0.0.1 --port 8000
    Nginx proxies /api/* to this process; /web/* is served directly by Nginx.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import chats, messages, deleted, stats, health, backfill, telethon


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler (replaces the deprecated on_event pattern).

    Startup: nothing to initialise — read connections are opened per-request in the dependency.
    We log readiness so the systemd journal shows a clear start signal.

    Shutdown: same — connections are closed by the dependency's finally block.
    Any cleanup that becomes necessary in later phases goes here.
    """
    import logging
    logging.getLogger(__name__).info("TeleVault API starting up.")
    yield
    logging.getLogger(__name__).info("TeleVault API shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TeleVault API",
    description=(
        "Read-only REST API for the TeleVault personal Telegram archive. "
        "All write operations are performed exclusively by the userbot process."
    ),
    version="1.1.0",
    # Disable the default /docs and /redoc in production by setting these to None.
    # Leave them enabled for now — useful during development.
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# API routes — all prefixed with /api to allow Nginx to proxy them cleanly
# ---------------------------------------------------------------------------

app.include_router(health.router,    prefix="/api")
app.include_router(chats.router,     prefix="/api")
app.include_router(messages.router,  prefix="/api")
app.include_router(deleted.router,   prefix="/api")
app.include_router(stats.router,     prefix="/api")
app.include_router(backfill.router,  prefix="/api")
app.include_router(telethon.router,  prefix="/api")


# ---------------------------------------------------------------------------
# Static files — web UI
# ---------------------------------------------------------------------------

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"

if _WEB_DIR.exists():
    # Mount at "/" so index.html is served at the root.
    # The API routes registered above take precedence because FastAPI matches them before falling through to StaticFiles.
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
else:
    import logging
    logging.getLogger(__name__).warning(
        "web/ directory not found at %s — static UI will not be served. "
        "This is expected before the frontend is built.",
        _WEB_DIR,
    )