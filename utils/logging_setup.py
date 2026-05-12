"""
Configures Python's standard logging for the whole application.
 
Output goes to two places simultaneously:
  - stdout (console), so you can watch it live or pipe it to journald on the VPS
  - a rotating log file, so you keep history without the file growing forever
 
The rotating file caps at 5 MB and keeps the last 3 files. That's enough to
diagnose issues that surfaced hours ago without eating disk space.
 
Log level is read from config so you can switch to DEBUG in .env when needed
without touching this file.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Max size per log file before rotation kicks in.
_MAX_BYTES = 5 * 1024 * 1024    # 5 MB

# Number of rotated backups to keep alongside the active file.
_BACKUP_COUNT = 3


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    """
    Set up the root logger with a console handler and, optionally, a rotating file handler.
 
    Call this once, early in main(), before any other module logs anything.
 
    Args:
        log_level: Any standard level name — 'DEBUG', 'INFO', 'WARNING', etc.
                   Case-insensitive. Defaults to 'INFO'.
        log_file:  Path to the log file. Rotation is applied automatically.
                   Pass None (or omit) to skip file logging entirely —
                   useful during local development when console is enough.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    fomatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    handlers: list[logging.Handler] = []

    # Console handler — always on
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fomatter)
    handlers.append(console)

    # File handler — only when a path is provided
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(fomatter)
        handlers.append(file_handler)
    

    logging.basicConfig(
        level=numeric_level,
        handlers=handlers
    )

    # Telethon is fairly verbose at DEBUG — keep it at WARNING unless you're
    # actively debugging the Telegram connection itself.
    logging.getLogger("telethon").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging initialised — level={log_level.upper()}"
        + (f", file={log_file}" if log_file else "")
    )