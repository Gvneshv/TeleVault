"""
Application entry point - start TeleVault with: python main.py
 
Startup sequence:
  1. Logging
  2. Database (open connection, apply schema)
  3. Telethon client (authenticate if needed, then connect)
  4. Register event handlers
  5. Run until interrupted (Ctrl-C or SIGTERM)
  6. Graceful shutdown
 
Telethon uses asyncio internally, so the entry point is an async function run via asyncio.run().
Everything Telegram-related happens inside that loop.
"""

import asyncio
import logging
import signal

from telethon import TelegramClient

import db
from config import settings
from utils.logging_setup import setup_logging
from handlers import on_message, on_delete, on_edit


logger = logging.getLogger(__name__)


def register_handlers(client: TelegramClient, self_id: int) -> None:
    """
    Attach all Telethon event handlers to the client.
 
    Each handler module registers itself when imported (via @client.on(...) decorators), but the client reference must be injected first.
    The pattern used in each handler module is:
 
        def register(client): ...  <- called here
        # rather than a bare module-level decorator
 
    This keeps the client out of module-level scope in the handler files and makes unit testing easier - you can call register(mock_client) without needing a real Telethon connection.

    self_id (the archiving account's own Telegram user ID) is passed to on_delete specifically:
    it's needed to recognize Saved Messages (the one chat where chat_id == your own user ID)
    for deletion-actor inference — only the account owner has access to their own Saved Messages, so any deletion there is deterministically 'self', not a guess.
    See db/queries.py's flag_deleted() for where this is actually used.
    """
    on_message.register(client)
    on_delete.register(client, self_id)
    on_edit.register(client)
    logger.info("Event handlers registered.")
  

async def main() -> None:
    # ------------------------------------------------------------------ #
    # 1. Logging                                                          
    # ------------------------------------------------------------------ #
    setup_logging(log_level=settings.log_level, log_file=settings.log_file)
    logger.info("Starting TeleVault...")

    # ------------------------------------------------------------------ #
    # 2. Database                                                         
    # ------------------------------------------------------------------ #
    conn = db.init_db(settings.db_path)
    db.apply_schema(conn)

    # ------------------------------------------------------------------ #
    # 3. Telethon client                                                  
    # ------------------------------------------------------------------ #
    # The session file persists the login so you only enter the auth code once.
    # After that, Telethon reuses the saved session automatically.
    client = TelegramClient(
        settings.session_name,
        settings.api_id,
        settings.api_hash,
    )

    await client.start(phone=settings.phone)

    me = await client.get_me()
    logger.info(f"Authenticated as: {me.first_name} (id={me.id})")

    # ------------------------------------------------------------------ #
    # 4. Event handlers                                                   
    # ------------------------------------------------------------------ #
    register_handlers(client, self_id=me.id)

    # ------------------------------------------------------------------ #
    # 5. Run                                                              
    # ------------------------------------------------------------------ #
    logger.info("TeleVault is running. Press Ctrl-C to stop.")

    # Handle SIGTERM gracefully (sent by systemd or Docker on shutdown) add_signal_handler() is Unix-only - Windows raises NotImplementedError.
    # On Windows, Ctrl-C (SIGINT) via the KeyboardInterrupt except below is the only shutdown path needed during local development anyway.
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
    except NotImplementedError:
        # Expected on Windows. SIGTERM is a Unix concept; skip silently.
        pass

    try:
        await client.run_until_disconnected()
    except (KeyboardInterrupt, asyncio.CancelledError):
        # KeyboardInterrupt : Ctrl-C on all platforms.
        # CancelledError    : Python 3.14 changed asyncio shutdown - the main task is now cancelled rather than allowed to return cleanly, so CancelledError surfaces here instead.
        pass
    
    # ------------------------------------------------------------------ #
    # 6. Shutdown                                                         
    # ------------------------------------------------------------------ #
    logger.info("Shutting down...")
    await client.disconnect()
    db.close_db()
    logger.info("Goodbye.")
  

if __name__ == "__main__":
    # Wrap asyncio.run() so that Ctrl-C or a SIGTERM-triggered CancelledError reaching this level exits silently rather than printing a traceback.
    # The actual shutdown logic (disconnect, close_db) is inside main(), which handles both exceptions there.
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass