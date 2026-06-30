"""
db — TeleVault database package.
 
Re-exports the public interface so the rest of the application imports from one place rather than knowing which submodule each symbol lives in:
 
    from db import init_db, apply_schema, queries
 
Internal reorganisation (splitting queries.py, moving connection logic, etc.) won't break any caller as long as these exports stay stable.
"""

from db.connection import init_db, close_db, get_connection
from db.schema import apply_schema
from db import queries
from .read_queries import (
    get_chats,
    get_chat,
    get_messages,
    get_chat_messages,
    get_message_detail,
    get_stats,
    get_message_count,
)


__all__ = ["init_db", "close_db", "get_connection", "apply_schema", "queries", "get_chats", "get_chat", "get_messages", "get_chat_messages", "get_message_detail", "get_stats", "get_message_count"]