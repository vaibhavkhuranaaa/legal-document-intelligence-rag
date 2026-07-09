import logging

import pytest
from azure.ai.documentintelligence.models import (
    AnalyzeResult,
    BoundingRegion,
    DocumentPage,
    DocumentParagraph,
)

from legal_rag.ingestion.config import IngestionSettings
from legal_rag.ingestion.exceptions import AzureServiceError
from legal_rag.ingestion.models import ExtractionStatus
from legal_rag.ingestion.normalization import NormalizedDocument
from legal_rag.ingestion.pipeline import run_pipeline
from tests.ingestion.conftest import FakeStorageBackend


class _FakeAzureClient:
    """Test double for `AzureDocumentIntelligenceClient` — no network, no SDK poller."""

    def __init__(self, responses: dict[str, AnalyzeResult | Exception]) -> None:
        self._responses = responses

    def analyze(self, document: NormalizedDocument) -> AnalyzeResult:
        response = self._responses[document.ref]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def settings() -> IngestionSettings:
    return IngestionSettings(
        azure_document_intelligence_endpoint="https://example.cognitiveservices.azure.com/",
        azure_document_intelligence_api_key="dummy-key",
        pipeline_version="1.0.0-test",
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("legal_rag.ingestion.test.pipeline")


def _page(page_number: int = 1) -> DocumentPage:
    return DocumentPage(page_number=page_number, width=8.5, height=11.0, unit="inch", spans=[])


def _paragraph(text: str, page_number: int = 1) -> DocumentParagraph:
    return DocumentParagraph(
        role=None,
        content=text,
        bounding_regions=[BoundingRegion(page_number=page_number, polygon=[0, 0, 1, 1])],
        spans=[],
    )


def _analyze_result(paragraphs: list[DocumentParagraph] | None = None) -> AnalyzeResult:
    return AnalyzeResult(
        api_version="2024-11-30",
        model_id="prebuilt-layout",
        content="",
        pages=[_page()],
        paragraphs=paragraphs if paragraphs is not None else [_paragraph("Body text.")],
        tables=[],
    )


def test_run_pipeline_processes_single_document_successfully(
    settings: IngestionSettings, logger: logging.Logger
) -> None:
    storage = FakeStorageBackend({"merger.pdf": b"%PDF-fake-content"})
    client = _FakeAzureClient({"merger.pdf": _analyze_result()})

    report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)  # type: ignore[arg-type]

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.extraction_status == ExtractionStatus.SUCCESS
    assert entry.document_id is not None
    assert entry.source_file == "merger.pdf"
    assert entry.error is None
    assert entry.output_path is not None
    assert entry.document_id in storage.written_processed
    assert report.run_id in storage.written_reports
    assert report.pipeline_version == "1.0.0-test"


def test_run_pipeline_records_unsupported_format_as_failure(
    settings: IngestionSettings, logger: logging.Logger
) -> None:
    storage = FakeStorageBackend({"notes.txt": b"plain text, not a real document"})
    client = _FakeAzureClient({})

    report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)  # type: ignore[arg-type]

    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.extraction_status == ExtractionStatus.FAILED
    assert entry.document_id is None
    assert entry.correlation_id in storage.written_failed
    assert "UnsupportedFormatError" in (entry.error or "")


def test_run_pipeline_records_azure_failure_and_continues_batch(
    settings: IngestionSettings, logger: logging.Logger
) -> None:
    storage = FakeStorageBackend({"good.pdf": b"%PDF-good", "broken.pdf": b"%PDF-broken"})
    client = _FakeAzureClient(
        {
            "good.pdf": _analyze_result(),
            "broken.pdf": AzureServiceError("service unavailable"),
        }
    )

    report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)  # type: ignore[arg-type]

    assert len(report.entries) == 2
    by_ref = {entry.source_file: entry for entry in report.entries}
    assert by_ref["good.pdf"].extraction_status == ExtractionStatus.SUCCESS
    assert by_ref["broken.pdf"].extraction_status == ExtractionStatus.FAILED
    assert "AzureServiceError" in (by_ref["broken.pdf"].error or "")


def test_run_pipeline_records_semantic_validation_failure_with_preserved_document_id(
    settings: IngestionSettings, logger: logging.Logger
) -> None:
    storage = FakeStorageBackend({"blank.pdf": b"%PDF-blank-scan"})
    client = _FakeAzureClient({"blank.pdf": _analyze_result(paragraphs=[])})

    report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)  # type: ignore[arg-type]

    entry = report.entries[0]
    assert entry.extraction_status == ExtractionStatus.FAILED
    assert entry.document_id is not None
    assert "SemanticValidationError" in (entry.error or "")


def test_run_pipeline_isolates_unexpected_exceptions(
    settings: IngestionSettings, logger: logging.Logger
) -> None:
    storage = FakeStorageBackend({"buggy.pdf": b"%PDF-buggy"})
    client = _FakeAzureClient({"buggy.pdf": RuntimeError("unexpected bug")})

    report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)  # type: ignore[arg-type]

    entry = report.entries[0]
    assert entry.extraction_status == ExtractionStatus.FAILED
    assert entry.document_id is None
    assert "unexpected internal error" in (entry.error or "")


def test_run_pipeline_with_no_documents_still_writes_report(
    settings: IngestionSettings, logger: logging.Logger
) -> None:
    storage = FakeStorageBackend({})
    client = _FakeAzureClient({})

    report = run_pipeline(settings=settings, storage=storage, client=client, logger=logger)  # type: ignore[arg-type]

    assert report.entries == []
    assert report.run_id in storage.written_reports
