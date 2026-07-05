"""
Logging utility for the application.

Sets up console and rotating file handlers with a structured format.
Provides typed convenience wrappers: info(), debug(), error().
"""

from __future__ import annotations

import datetime
import logging
import logging.handlers
from pathlib import Path


# ---------------------------------------------------------------------------
# Log directory
# ---------------------------------------------------------------------------

LOG_DIR = Path("local_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

FORMATTER = logging.Formatter(
    fmt="{asctime} | {levelname:<8} | {name} | {module}:{funcName}:{lineno} | {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# Root logger
# ---------------------------------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Guard against duplicate handlers if this module is imported multiple times
if not logger.handlers:
    # --- Console handler ---
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.INFO)
    _console_handler.setFormatter(FORMATTER)
    logger.addHandler(_console_handler)

    # --- Daily rotating file handler ---
    _log_filename = LOG_DIR / f"{datetime.date.today().strftime('%m-%d-%Y')}.log"
    _file_handler = logging.FileHandler(filename=_log_filename, mode="a", encoding="utf-8")
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(FORMATTER)
    logger.addHandler(_file_handler)


# ---------------------------------------------------------------------------
# Filter helpers (unused by default — attach manually if needed)
# ---------------------------------------------------------------------------

class InfoFilter(logging.Filter):
    """Pass only INFO-level records."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelname == "INFO"


class DebugFilter(logging.Filter):
    """Pass only DEBUG-level records."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelname == "DEBUG"


class ErrorCriticalFilter(logging.Filter):
    """Pass only ERROR and CRITICAL records."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelname in ("ERROR", "CRITICAL")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def info(msg: object) -> None:
    """Log *msg* at INFO level."""
    logging.info(msg)


def debug(msg: object) -> None:
    """Log *msg* at DEBUG level."""
    logging.debug(msg)


def error(msg: object) -> None:
    """Log *msg* at ERROR level, including exception info if available."""
    logging.error(msg, exc_info=True)
