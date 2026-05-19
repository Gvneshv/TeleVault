# TeleVault

A personal Telegram userbot that archives all your messages in real time and
preserves deleted ones so you can retrieve them later.

**Phase 1 scope:** text messages only, all chat types, local SQLite storage.

---

## Requirements

- Python 3.11 or newer
- A Telegram account
- Telegram API credentials (free - takes two minutes to get)

---

## 1. Get your Telegram API credentials

1. Go to **https://my.telegram.org** and log in with your phone number.
2. Click **"API development tools"**.
3. Fill in any app name and short name (e.g. `televault` / `tvault`) - these
   are just labels, they don't affect anything.
4. Copy your **App api_id** (a number) and **App api_hash** (a hex string).

> Keep these secret. Anyone with your api_id + api_hash can impersonate your
> app (though not your account without the login code).

---

## 2. Set up the project

```bash
# Clone the repo
git clone https://github.com/Gvneshv/TeleVault.git
cd TeleVault

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 3. Configure

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
TG_API_ID=12345678
TG_API_HASH=0123456789abcdef0123456789abcdef
TG_PHONE=+1234567890          # your number in international format
```

The other settings have sensible defaults - you can leave them as-is for now.

---

## 4. First run

```bash
python main.py
```

**First-time only:** Telethon will prompt you for the verification code that
Telegram sends to your account (just like logging into a new device). Enter
it and press Enter. A `televault.session` file is created - this stores your
login so you won't be asked again.

You should see output like:

```
2026-05-12 18:00:00  INFO      utils.logging_setup    Logging initialised - level=INFO
2026-05-12 18:00:01  INFO      __main__               Starting TeleVault.
2026-05-12 18:00:02  INFO      __main__               Authenticated as: Alice (id=123456789)
2026-05-12 18:00:02  INFO      __main__               Event handlers registered.
2026-05-12 18:00:02  INFO      __main__               TeleVault is running. Press Ctrl-C to stop.
```

From this point, TeleVault is archiving every text message in real time.

---

## 5. Smoke test

With TeleVault running, open Telegram on your phone or desktop and:

1. **Send yourself a message** (open Saved Messages and type anything).
   You should see a log line:
   ```
   INFO  db.queries  Inserted message 1 from chat 123456789 -> internal id 1
   ```

2. **Delete that message.**
   You should see:
   ```
   INFO  db.queries  Flagged message 1 in chat 123456789 as deleted at ...
   ```

3. **Query the database directly** to confirm:
   ```bash
   sqlite3 data/televault.db "
     SELECT text, is_deleted, deleted_at
     FROM messages
     ORDER BY archived_at DESC
     LIMIT 5;
   "
   ```

---

## 6. Stopping TeleVault

Press **Ctrl-C**. The shutdown is graceful - the database connection is
flushed and closed cleanly before the process exits.

---

## Project structure

```
televault/
├── main.py              # Entry point
├── config.py            # Settings loader (.env -> Settings dataclass)
├── db/
│   ├── connection.py    # SQLite connection management
│   ├── schema.py        # Table definitions (run on every startup)
│   └── queries.py       # All read/write operations
├── handlers/
│   ├── helpers.py       # Shared Telethon entity utilities
│   ├── on_message.py    # NewMessage handler
│   ├── on_delete.py     # MessageDeleted handler
│   └── on_edit.py       # MessageEdited handler
└── utils/
    └── logging_setup.py # Console + rotating file logging
```

---

## Notes

- **`.session` file:** treat it like a password. It lets anyone run requests
  as your Telegram account. It's excluded from git via `.gitignore`.
- **Telegram ToS:** TeleVault archives only messages from chats you're already
  part of, for personal use. It doesn't automate sending, scrape public
  content, or interact with other accounts - it stays well within the
  acceptable personal-use boundary.
- **Media messages** (photos, stickers, voice notes) are silently skipped in
  Phase 1. The log will show a `DEBUG` line for each skipped message if you
  set `LOG_LEVEL=DEBUG` in `.env`.