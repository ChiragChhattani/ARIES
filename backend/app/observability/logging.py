"""
Structured logging configuration for ARIES.

WHY STRUCTURED LOGGING?
-----------------------
Traditional logs like "Interview started for session abc" are human-readable
but hard to search, filter, and aggregate programmatically. Structured logging
attaches machine-readable key-value fields to every log entry:

    {"event": "interview_started", "session_id": "abc", "timestamp": "..."}

This lets us:
- Filter by session_id in log aggregators (e.g., "show me all logs for session X")
- Correlate events across agents using correlation_id
- Track latency by pairing start/end events
- Redact sensitive fields systematically

CORRELATION IDS
--------------
A correlation_id is a unique identifier that follows a request through every
layer of the system. When a user creates an interview, the same correlation_id
appears in the API handler log, the orchestrator log, the agent log, and the
database log. This lets you trace a single operation across all components.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any
from contextvars import ContextVar

# ContextVar stores per-request state in async code without threading issues.
# Each concurrent request gets its own correlation_id automatically.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="no-correlation-id")
session_id_var: ContextVar[str] = ContextVar("session_id", default="no-session")


class StructuredFormatter(logging.Formatter):
    """
    Formats log records as JSON with structured fields.

    Each log entry includes:
    - timestamp: ISO 8601 UTC timestamp
    - level: Log level (DEBUG, INFO, etc.)
    - logger: Logger name (usually the module path)
    - message: The log message
    - correlation_id: Request-scoped tracking ID
    - session_id: Interview session ID (when available)
    - Extra fields: Any additional key-value pairs passed to the logger
    """

    # Fields that are part of the standard LogRecord and should NOT
    # be included as extra structured data
    RESERVED_ATTRS = {
        "args", "asctime", "created", "exc_info", "exc_text",
        "filename", "funcName", "levelname", "levelno", "lineno",
        "module", "msecs", "message", "msg", "name", "pathname",
        "process", "processName", "relativeCreated", "stack_info",
        "taskName", "thread", "threadName",
    }

    # Fields that must NEVER appear in logs (redacted if present)
    SENSITIVE_FIELDS = {"api_key", "openai_api_key", "password", "token", "secret"}

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
            "session_id": session_id_var.get(),
        }

        # Add any extra fields the caller passed (e.g., logger.info("msg", extra={"agent": "interviewer"}))
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith("_"):
                # Redact sensitive fields
                if key.lower() in self.SENSITIVE_FIELDS:
                    log_entry[key] = "***REDACTED***"
                else:
                    log_entry[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure the root logger for ARIES.

    Args:
        log_level: Minimum log level to emit.
        json_output: If True, emit structured JSON. If False, use human-readable format.
                     Use json_output=False during local development for readability.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove any existing handlers (prevents duplicate logs on reload)
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if json_output:
        handler.setFormatter(StructuredFormatter())
    else:
        # Human-readable format for development
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        ))

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger for a module.

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened", extra={"session_id": "abc"})
    """
    return logging.getLogger(f"aries.{name}")
