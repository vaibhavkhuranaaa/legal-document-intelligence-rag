"""Orchestrates the ingestion pipeline end to end.

This module contains orchestration only: call sequencing through the stages
approved in the Phase 1 design (discovery → normalization → Azure →
adapter → structure → mapping → validation → storage → manifest), exception
handling that turns a per-document failure into a `ManifestEntry` without
aborting the batch, run/correlation ID bookkeeping, logging, and the single
`DocumentRecord.model_dump_json()` serialization call. No format detection,
heading heuristics, schema construction, retry logic, or validation rules
live here — those belong to the modules that already implement them.

`run_pipeline` receives every dependency (settings, storage, client, logger)
by injection and constructs no infrastructure itself, so it can run
unchanged against a local filesystem today or an Azure Function invocation
later (see Section 7 of the Phase 1 design and ADR-0005).
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pydantic

from legal_rag.ingestion.adapter import to_raw_document
from legal_rag.ingestion.client import AzureDocumentIntelligenceClient
from legal_rag.ingestion.config import IngestionSettings
from legal_rag.ingestion.discovery import SourceDocument, discover
from legal_rag.ingestion.exceptions import (
    IngestionError,
    SchemaValidationError,
    SemanticValidationError,
)
from legal_rag.ingestion.logging_config import bind_context
from legal_rag.ingestion.mapper import SourceFileInfo, to_document_record
from legal_rag.ingestion.models import ExtractionStatus, ManifestEntry, RunReport
from legal_rag.ingestion.normalization import normalize
from legal_rag.ingestion.storage.base import StorageBackend
from legal_rag.ingestion.structure import build_structure
from legal_rag.ingestion.validation import validate


def _generate_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"


@dataclass
class _PipelineContext:
    storage: StorageBackend
    client: AzureDocumentIntelligenceClient
    settings: IngestionSettings
    logger: logging.Logger
    run_id: str


def _process_document_inner(
    source_document: SourceDocument,
    *,
    context: _PipelineContext,
    correlation_id: str,
    start: float,
) -> ManifestEntry:
    normalized = normalize(source_document, context.storage)
    analyze_result = context.client.analyze(normalized)
    raw_document = to_raw_document(analyze_result)
    document_structure = build_structure(raw_document)
    record = to_document_record(
        document_structure=document_structure,
        raw_document=raw_document,
        source=SourceFileInfo(
            file_name=source_document.ref.rsplit("/", 1)[-1],
            file_path=source_document.ref,
            content=normalized.content,
        ),
        pipeline_version=context.settings.pipeline_version,
        extracted_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.SUCCESS,
        warnings=document_structure.warnings,
    )

    validation_result = validate(record)
    if not validation_result.is_valid:
        raise SemanticValidationError(
            f"document failed semantic validation: {source_document.ref!r}",
            context={"errors": validation_result.errors, "document_id": record.document_id},
        )

    output_path = context.storage.write_processed_document(
        record.document_id, record.model_dump_json(indent=2).encode("utf-8")
    )
    duration = time.monotonic() - start
    context.logger.info(
        "document processed",
        extra={
            "document_id": record.document_id,
            "processing_duration_seconds": duration,
            "extraction_status": record.extraction.status.value,
            "warning_count": len(record.extraction.warnings),
            "page_count": record.page_count,
        },
    )
    return ManifestEntry(
        document_id=record.document_id,
        run_id=context.run_id,
        correlation_id=correlation_id,
        source_file=source_document.ref,
        processing_duration_seconds=duration,
        page_count=record.page_count,
        output_path=output_path,
        warnings=record.extraction.warnings,
        extraction_status=record.extraction.status,
    )


def _handle_failure(
    error: IngestionError,
    source_document: SourceDocument,
    *,
    context: _PipelineContext,
    correlation_id: str,
    start: float,
) -> ManifestEntry:
    duration = time.monotonic() - start
    document_id = error.context.get("document_id")

    failure_payload = {
        "ref": source_document.ref,
        "run_id": context.run_id,
        "correlation_id": correlation_id,
        "document_id": document_id,
        "error_type": type(error).__name__,
        "error_message": error.message,
        "context": error.context,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    output_path = context.storage.write_failure_record(
        correlation_id, json.dumps(failure_payload, indent=2, default=str).encode("utf-8")
    )
    context.logger.error(
        "document processing failed",
        extra={
            "document_id": document_id,
            "error_type": type(error).__name__,
            "processing_duration_seconds": duration,
            "extraction_status": ExtractionStatus.FAILED.value,
        },
    )
    return ManifestEntry(
        document_id=document_id,
        run_id=context.run_id,
        correlation_id=correlation_id,
        source_file=source_document.ref,
        processing_duration_seconds=duration,
        page_count=None,
        output_path=output_path,
        warnings=[],
        extraction_status=ExtractionStatus.FAILED,
        error=f"{type(error).__name__}: {error.message}",
    )


def _process_document(
    source_document: SourceDocument, *, context: _PipelineContext
) -> ManifestEntry:
    correlation_id = uuid4().hex
    start = time.monotonic()

    with bind_context(
        run_id=context.run_id, correlation_id=correlation_id, ref=source_document.ref
    ):
        try:
            return _process_document_inner(
                source_document, context=context, correlation_id=correlation_id, start=start
            )
        except pydantic.ValidationError as exc:
            error: IngestionError = SchemaValidationError(
                f"document failed schema validation: {source_document.ref!r}",
                context={"errors": exc.errors()},
            )
        except IngestionError as exc:
            error = exc
        except Exception as exc:  # noqa: BLE001 - deliberate per-document isolation
            context.logger.error(
                "unexpected internal pipeline failure",
                exc_info=True,
                extra={"ref": source_document.ref},
            )
            error = IngestionError(
                f"unexpected internal error processing {source_document.ref!r}: {exc}",
                context={"unexpected": True},
            )

        return _handle_failure(
            error, source_document, context=context, correlation_id=correlation_id, start=start
        )


def run_pipeline(
    *,
    settings: IngestionSettings,
    storage: StorageBackend,
    client: AzureDocumentIntelligenceClient,
    logger: logging.Logger,
) -> RunReport:
    """Process every discoverable document and return the run's manifest report."""
    run_id = _generate_run_id()
    started_at = datetime.now(UTC)
    context = _PipelineContext(
        storage=storage, client=client, settings=settings, logger=logger, run_id=run_id
    )

    with bind_context(run_id=run_id):
        logger.info("ingestion run started", extra={"run_id": run_id})

        entries = [
            _process_document(source_document, context=context)
            for source_document in discover(storage)
        ]

        completed_at = datetime.now(UTC)
        report = RunReport(
            run_id=run_id,
            pipeline_version=settings.pipeline_version,
            started_at=started_at,
            completed_at=completed_at,
            entries=entries,
        )

        succeeded = sum(
            1 for entry in entries if entry.extraction_status == ExtractionStatus.SUCCESS
        )
        logger.info(
            "ingestion run completed",
            extra={
                "run_id": run_id,
                "documents_total": len(entries),
                "documents_succeeded": succeeded,
                "documents_failed": len(entries) - succeeded,
            },
        )
        storage.write_run_report(run_id, report.model_dump_json(indent=2).encode("utf-8"))

    return report
