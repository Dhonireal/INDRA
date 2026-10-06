"""
VisionPilot Structured Logger.

Provides formatted logging to console and rotating log file with automatic
credential and sensitive token redaction complying with Rule 6 and Rule 26.
"""
import logging
import re
from typing import Optional
from pathlib import Path
from app.core.config import config

# Patterns to automatically redact in logs
REDACTION_PATTERNS = [
    re.compile(r"(?i)(password\s*[:=]\s*)['\"]?([^\s'\"&]+)['\"]?"),
    re.compile(r"(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{15,}"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)['\"]?([^\s'\"&]+)['\"]?"),
    re.compile(r"(?i)(token\s*[:=]\s*)['\"]?([^\s'\"&]+)['\"]?"),
    re.compile(r"(?i)(secret\s*[:=]\s*)['\"]?([^\s'\"&]+)['\"]?"),
]


class RedactingFormatter(logging.Formatter):
    """Formatter that masks sensitive tokens, passwords, and API keys."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern in REDACTION_PATTERNS:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        return redacted


def setup_logger(name: str = "VisionPilot") -> logging.Logger:
    """Configures and returns the application logger."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = RedactingFormatter(fmt=log_format, datefmt=date_format)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if config.log_to_file:
        log_file: Path = config.logs_dir / config.log_file_name
        try:
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not initialize log file at {log_file}: {e}")

    return logger


# Global logger instance
logger = setup_logger()
