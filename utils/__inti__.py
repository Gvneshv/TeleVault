"""
utils — Shared infrastructure for TeleVault.
 
Anything that doesn't belong to the database layer or the Telegram event
handlers lives here. Currently that's just logging setup, but this is the
natural home for future helpers (e.g. text sanitisation, retry decorators).
 
Usage:
 
    from utils import setup_logging
"""

from utils.logging_setup import setup_logging

__all__ = ["setup_logging"]