"""
Loads all runtime configuration from environment variables (via a .env file).
 
The settings are exposed as a single frozen dataclass instance — `settings` —
imported directly wherever needed:
 
    from config import settings
    print(settings.db_path)
 
Why a dataclass rather than reading os.environ inline?
  - One import gives you everything; no hunting for os.getenv() calls scattered
    around the codebase.
  - The frozen=True flag prevents accidental mutation after startup.
  - Type annotations document what each setting is supposed to be.
  - Missing required values fail loudly at startup, not halfway through a run.
 
Required .env keys:       TG_API_ID, TG_API_HASH, TG_PHONE
Optional (have defaults): DB_PATH, SESSION_NAME, LOG_LEVEL, LOG_FILE
"""

import os
import sys
import logging
from dataclasses import dataclass
from pathlib import Path

# python-dotenv reads the .env file and injects values into os.environ.
# It does nothing if the variables are already set (e.g. in a real shell
# environment on the VPS), so it's safe to leave this call in production.
try:
    from dotenv import load_dotenv
except ImportError:
    # Fail clearly rather than silently running without .env support.
    sys.exit(
        "ERROR: Python package 'python-dotenv' is required.\n"
        "Install it with 'pip install python-dotenv' and try again."
    )


logger = logging.getLogger(__name__)


# Resolve .env relative to this file, not the working directory.
# That way `python -m televault` works from any directory.
_ENV_PATH = Path(__file__).parent / ".env"

# Load environment variables from .env file.
load_dotenv(_ENV_PATH)


def _require(key: str) -> str:
    """
    Read a required environment variable.
    Exits immediately with a clear message if it's missing or empty.
    """
    value = os.getenv(key, "").strip()
    if not value:
        sys.exit(
            f"[config] Required environment variable '{key}' is not set. "
            f"Check your .env file."
        )
    return value

def _optional(key: str, default: str) -> str:
    """
    Read an optional environment variable, falling back to a default.
    """
    return os.getenv(key, default).strip() or default


@dataclass(frozen=True)
class Settings:
    """
    All runtime configuration for TeleVault.
 
    Frozen so nothing can accidentally overwrite a setting after startup.
    Attributes map 1-to-1 with .env keys (lowercased and without the TG_ prefix
    where they're Telegram-specific).
    """

    # --- Telegram credentials ---
    # Obtain these from https://my.telegram.org → API development tools.
    # Treat them like passwords: never commit, never log.
    api_id: int
    api_hash: str
    phone: str

    # Name for the Telethon session file (stored as <name>.session).
    # Changing this forces a fresh login — keep it stable.
    session_name: str

    # --- Storage ---
    db_path: str

    # --- Logging ---
    log_level: str          # 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
    log_file: str | None    # None means log to console only


def _load() -> Settings:
    """
    Build the Settings instance from environment variables.
    Called once at module import time.
    """
    raw_api_id = _require("TG_API_ID")
    try:
        api_id = int(raw_api_id)
    except ValueError:
        sys.exit(
            f"[config] TG_API_ID must be an integer, got: {raw_api_id!r}"
        )
    
    log_file_raw = _optional("LOG_FILE", "")
    log_file = log_file_raw if log_file_raw else None

    return Settings(
        api_id=         api_id,
        api_hash=       _require("TG_API_HASH"),
        phone=          _require("TG_PHONE"),
        session_name=   _optional("SESSION_NAME", "televault"),
        db_path=        _optional("DB_PATH", "data/televault.db"),
        log_level=      _optional("LOG_LEVEL", "INFO"),
        log_file=       log_file,
    )


# The single shared instance.  Import this everywhere.
settings = _load()