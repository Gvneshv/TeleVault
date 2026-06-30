# Changelog

All notable changes to TeleVault will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned — Phase 2 (Web UI)

- REST API layer (`api/` package) built with FastAPI + Uvicorn
- Read-only database query layer for the API (`get_messages`, `get_chats`, `get_deleted`, `get_stats`)
- Pydantic v2 response schemas for all API endpoints
- Endpoints: `/api/chats`, `/api/chats/{id}/messages`, `/api/messages`, `/api/messages/{id}`, `/api/deleted`, `/api/stats`, `/api/health`
- Single-page vanilla JS web UI (`web/` package) served as static files
- Views: chat list, message browser, deleted messages, global search, stats dashboard
- PWA support: `manifest.json` + service worker for installable app on all platforms
- Call service messages now stored with humanized text labels ([Missed call], [Voice call · N min], etc.) instead of NULL

### Planned — Phase 3 (Advanced Features)

- Full-text search via SQLite FTS5 virtual table
- Backfill: archive historical messages sent before TeleVault was running
- Chat filter: allowlist/blocklist to control which chats are archived
- Storage mode: `all` (default) vs `deletions_only`
- Display name overrides: map a friendly label to a sender ID
- Username change tracking (`username_history` table)
- Auto-read policies: mark selected chats as read on a schedule
- Data management: clear all data, clear per-chat data (with irreversibility warning)
- Message ignore rules: filter by chat or text pattern before archiving
- TTL / retention policy: auto-delete archived messages older than N months

### Planned — Phase 4 (Infrastructure & Expansion)

- Media archiving (photos, documents, voice notes) with disk management
- PostgreSQL migration (swap SQLite for PostgreSQL + SQLAlchemy + Alembic)
- Orphan cleanup scheduler: reconcile DB records vs files on disk
- Notifications: Web Push via service worker (requires HTTPS)
- Read receipt inference: track `read_inbox_max_id` per chat (private chats only)
- Reactions tracking (`message_reactions` snapshot table) — low priority

---

## Added

- Pydantic v2 response schemas: `ChatOut`, `ChatSummary`, `MessageOut`,
  `MessageDetail`, `SenderOut`, `EditOut`, `DeletionOut`, `StatsOut`,
  `PaginatedResponse`, `HealthOut`

---

## [1.0.0] — 2026-05-29

### Summary

Phase 1 complete. Real-time text message archiving across all chat types.
Deleted messages are flagged and preserved. Edit history is tracked.
Stable enough for always-on deployment.

### Added

- `main.py` — async entry point; graceful shutdown on Ctrl-C (all platforms) and SIGTERM (Unix)
- `config.py` — frozen `Settings` dataclass loaded from `.env` via `python-dotenv`
- `db/connection.py` — SQLite connection with WAL mode, FK enforcement, and ISO 8601 datetime adapter
- `db/schema.py` — DDL for `chats`, `senders`, `messages`, `message_edits`, `message_deletions` tables; applied on every startup
- `db/queries.py` — all read/write operations with explicit `commit` / `rollback` (no context-manager transactions)
- `db/__init__.py` — package interface re-exporting `init_db`, `get_connection`, `close_db`, `apply_schema`
- `handlers/on_message.py` — `NewMessage` handler; upserts chat and sender rows defensively before inserting the message
- `handlers/on_delete.py` — `MessageDeleted` handler; falls back to `tg_message_id`-only lookup for private/group chats where `chat_id` is absent
- `handlers/on_edit.py` — `MessageEdited` handler; skips recording when `old_text == new_text` (Telegram fires edits for non-text changes)
- `handlers/helpers.py` — shared utilities: `get_chat_type()`, `get_sender_fields()`
- `utils/logging_setup.py` — console + rotating file handler (5 MB × 3 backups); Telethon pinned to WARNING
- `.env.example` — documented environment variable template
- `.gitattributes` — enforces LF line endings on Windows checkouts
- `requirements.txt` — pinned dependencies: `telethon`, `python-dotenv`
- `README.md` — setup guide, smoke test instructions, project structure, Telegram ToS note

### Schema (v3)

```
chats          (chat_id PK, name, username, chat_type, first_seen)
senders        (sender_id PK, username, first_name, last_name, first_seen)
messages       (id PK, tg_message_id, chat_id FK, sender_id FK, text,
                date, is_edited, edited_at, is_deleted, deleted_at, archived_at)
               UNIQUE INDEX on (tg_message_id, chat_id)
message_edits  (id PK, message_id FK, old_text, new_text, edited_at)
message_deletions (id PK, message_id FK, text_snapshot, deleted_at)
```

### Known Telegram protocol behaviours (documented)

- `MessageDeleted` carries no `chat_id` in private/group chats — fallback searches by `tg_message_id` alone
- Scheduled/auto-posted messages bypass `NewMessage`; arrive only as edit events — handled by defensive upsert
- Anonymous admin posts use the group's own (negative) ID as `sender_id` — stored as-is
- `MessageEdited` fires for link preview attachment, keyboard updates, view count increments — skipped when text is unchanged

### Technical decisions

- All datetimes stored as local-timezone ISO 8601 strings without milliseconds
- `detect_types` removed from SQLite connection — converter does not fire reliably in Python 3.14 module context
- `with conn:` (context manager) replaced with explicit `commit` / `rollback` — Python 3.12+ changed context manager semantics, breaking FK visibility across sequential writes
- Each DDL statement committed individually to avoid FK constraint failures under WAL snapshot isolation
- `upsert_chat` / `upsert_sender` accept `commit=False` to allow grouping all inserts into one transaction
- `loop.add_signal_handler(SIGTERM)` wrapped in `try/except NotImplementedError` for Windows compatibility

---

[Unreleased]: https://github.com/Gvneshv/TeleVault/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Gvneshv/TeleVault/releases/tag/v1.0.0
