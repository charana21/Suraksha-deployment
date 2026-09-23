"""
Structured logging configuration for CrowdVision

Provides:
- Console logging (always enabled)
- File logging with rotation (when LOG_FILE is set)
- JSON format for production
- Human-readable format for development
"""
import logging
import sys
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

class DailyFileHandler(TimedRotatingFileHandler):
    """
    TimedRotatingFileHandler variant where *today's* active file is itself
    named with the date (e.g. app-2026-07-20.log) instead of the plain
    base name only getting a date suffix once it's rotated out.
    """

    def __init__(self, base_path: str, backup_count: int = 30, encoding: str = "utf-8"):
        self._base_path = Path(base_path)
        self._stem = self._base_path.stem
        self._suffix = self._base_path.suffix or ".log"
        self._dir = self._base_path.parent
        super().__init__(
            str(self._dated_path()),
            when="midnight",
            backupCount=backup_count,
            encoding=encoding,
        )

    def _dated_path(self, when: Optional[float] = None) -> Path:
        date_str = datetime.fromtimestamp(when if when is not None else time.time()).strftime("%Y-%m-%d")
        return self._dir / f"{self._stem}-{date_str}{self._suffix}"

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None

        self.baseFilename = str(self._dated_path())

        if not self.delay:
            self.stream = self._open()

        self.rolloverAt = self.rolloverAt + self.interval
        while self.rolloverAt <= time.time():
            self.rolloverAt += self.interval


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_max_bytes: int = 10 * 1024 * 1024,
    log_backup_count: int = 5,
    app_env: str = "development"
) -> logging.Logger:
    """
    Configure application-wide logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Base path for the log file (None = console only). Actual
            file written each day is named with that day's date, e.g.
            passing "data-drive/logs/app.log" writes to
            "data-drive/logs/app-2026-07-20.log", rolling to a new dated
            file at midnight.
        log_max_bytes: Unused (kept for backwards-compat call signature)
        log_backup_count: Number of daily files to retain
        app_env: Environment (development/production)

    Returns:
        Root logger instance
    """
    # Get numeric log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Format based on environment
    if app_env == "production":
        # JSON-like format for production (easier to parse)
        log_format = '{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
        date_format = '%Y-%m-%dT%H:%M:%S'
    else:
        # Human-readable for development
        log_format = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'

    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = DailyFileHandler(
            log_file,
            backup_count=log_backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        root_logger.info(f"File logging enabled: {file_handler.baseFilename}")

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Usage:
        from utils.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Starting process...")

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
