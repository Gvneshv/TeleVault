"""
Application entry point — start TeleVault with: python main.py
 
Startup sequence:
  1. Logging
  2. Database (open connection, apply schema)
  3. Telethon client (authenticate if needed, then connect)
  4. Register event handlers
  5. Run until interrupted (Ctrl-C or SIGTERM)
  6. Graceful shutdown
 
Telethon uses asyncio internally, so the entry point is an async function
run via asyncio.run(). Everything Telegram-related happens inside that loop.
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


def register_handlers(client: TelegramClient) -> None:
    """
    Attach all Telethon event handlers to the client.
 
    Each handler module registers itself when imported (via @client.on(...)
    decorators), but the client reference must be injected first. The pattern
    used in each handler module is:
 
        def register(client): ...  <- called here
        # rather than a bare module-level decorator
 
    This keeps the client out of module-level scope in the handler files and
    makes unit testing easier - you can call register(mock_client) without
    needing a real Telethon connection.
    """
    on_message.register(client)
    on_delete.register(client)
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
    register_handlers(client)

    # ------------------------------------------------------------------ #
    # 5. Run                                                              
    # ------------------------------------------------------------------ #
    logger.info("TeleVault is running. Press Ctrl-C to stop.")

    # Handle SIGTERM gracefully (sent by systemd or Docker on shutdown)
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        # Ctrl-C — expected during local development; not an error
        pass
    
    # ------------------------------------------------------------------ #
    # 6. Shutdown                                                         
    # ------------------------------------------------------------------ #
    logger.info("Shutting down...")
    await client.disconnect()
    db.close_db()
    logger.info("Goodbye.")
  

if __name__ == "__main__":
    asyncio.run(main())