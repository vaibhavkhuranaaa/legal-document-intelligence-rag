import json
import logging

import pytest

from legal_rag.ingestion.logging_config import (
    JsonFormatter,
    bind_context,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def _reset_namespace_logger() -> None:
    namespace_logger = logging.getLogger("legal_rag")
    namespace_logger.handlers.clear()
    namespace_logger.propagate = True
    yield
    namespace_logger.handlers.clear()
    namespace_logger.propagate = True


def _make_record(message: str = "hello", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="legal_rag.ingestion.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_core_fields() -> None:
    formatter = JsonFormatter()

    payload = json.loads(formatter.format(_make_record("processing started")))

    assert payload["message"] == "processing started"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "legal_rag.ingestion.test"
    assert "timestamp" in payload


def test_json_formatter_includes_extra_fields() -> None:
    formatter = JsonFormatter()

    payload = json.loads(
        formatter.format(_make_record("done", processing_duration_seconds=1.23, page_count=5))
    )

    assert payload["processing_duration_seconds"] == 1.23
    assert payload["page_count"] == 5


def test_bind_context_injects_fields_within_scope() -> None:
    formatter = JsonFormatter()

    with bind_context(run_id="run-1", correlation_id="doc-1"):
        payload = json.loads(formatter.format(_make_record("inside scope")))

    assert payload["run_id"] == "run-1"
    assert payload["correlation_id"] == "doc-1"


def test_bind_context_does_not_leak_outside_scope() -> None:
    formatter = JsonFormatter()

    with bind_context(run_id="run-1"):
        pass
    payload = json.loads(formatter.format(_make_record("outside scope")))

    assert "run_id" not in payload


def test_bind_context_restores_previous_context_on_exit() -> None:
    formatter = JsonFormatter()

    with bind_context(run_id="run-1"):
        with bind_context(document_id="doc-1"):
            pass
        payload = json.loads(formatter.format(_make_record("back in outer scope")))

    assert payload["run_id"] == "run-1"
    assert "document_id" not in payload


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    configure_logging()

    namespace_logger = logging.getLogger("legal_rag")
    assert len(namespace_logger.handlers) == 1


def test_get_logger_returns_namespaced_logger() -> None:
    logger = get_logger("legal_rag.ingestion.pipeline")

    assert logger.name == "legal_rag.ingestion.pipeline"
