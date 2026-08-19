"""Structured logging for the ingestion pipeline.

Logs are emitted as single-line JSON via the standard library `logging`
module — no third-party logging framework. This keeps the design compatible
with a future Azure Monitor / OpenTelemetry integration: such an integration
would add another `logging.Handler` to the `legal_rag` logger (or wrap it
with an OpenTelemetry logging bridge), without requiring call sites to
change. Call sites always use `get_logger(__name__)` and standard `logging`
calls; they never format JSON themselves.

`bind_context` attaches run-scoped fields (e.g. `run_id`, `correlation_id`,
`document_id`) to every log record emitted within its scope, via a
`contextvars.ContextVar`, so callers don't have to thread those fields
through every log call by hand.
"""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_LOGGER_NAMESPACE = "legal_rag"

_STANDARD_LOG_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

_context: ContextVar[dict[str, Any] | None] = ContextVar("ingestion_log_context", default=None)


@contextmanager
def bind_context(**fields: Any) -> Iterator[None]:
    """Attach `fields` to every log record emitted within this scope."""
    current = _context.get() or {}
    token = _context.set({**current, **fields})
    try:
        yield
    finally:
        _context.reset(token)


class JsonFormatter(logging.Formatter):
    """Formats each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_context.get() or {})
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _STANDARD_LOG_RECORD_ATTRS
            }
        )
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the `legal_rag` logger namespace for structured JSON output.

    Idempotent: calling this more than once does not attach duplicate
    handlers. Only the `legal_rag` namespace is configured; the true root
    logger is left untouched.
    """
    namespace_logger = logging.getLogger(_LOGGER_NAMESPACE)
    namespace_logger.setLevel(level)
    if namespace_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    namespace_logger.addHandler(handler)
    namespace_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the `legal_rag` namespace."""
    return logging.getLogger(name)
