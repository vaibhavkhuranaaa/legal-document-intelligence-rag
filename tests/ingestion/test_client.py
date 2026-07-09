from dataclasses import dataclass
from typing import Any

import pytest
from azure.ai.documentintelligence import DocumentIntelligenceClient as AzureSdkClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.exceptions import HttpResponseError, ServiceRequestError

from legal_rag.ingestion.client import MODEL_ID, AzureDocumentIntelligenceClient
from legal_rag.ingestion.config import IngestionSettings
from legal_rag.ingestion.exceptions import AzureServiceError
from legal_rag.ingestion.normalization import NormalizedDocument


@pytest.fixture
def settings() -> IngestionSettings:
    return IngestionSettings(
        azure_document_intelligence_endpoint="https://example.cognitiveservices.azure.com/",
        azure_document_intelligence_api_key="dummy-key",
        _env_file=None,  # type: ignore[call-arg]
    )


@dataclass
class _FakePoller:
    result_value: AnalyzeResult | None = None
    error: Exception | None = None

    def result(self) -> AnalyzeResult:
        if self.error is not None:
            raise self.error
        assert self.result_value is not None
        return self.result_value


class _FakeSdkClient:
    """Test double standing in for `DocumentIntelligenceClient`."""

    def __init__(self, poller: _FakePoller) -> None:
        self._poller = poller
        self.calls: list[dict[str, Any]] = []

    def begin_analyze_document(
        self, model_id: str, body: bytes, *, content_type: str
    ) -> _FakePoller:
        self.calls.append({"model_id": model_id, "body": body, "content_type": content_type})
        return self._poller


def _document(
    content: bytes = b"%PDF-...", content_type: str = "application/pdf"
) -> NormalizedDocument:
    return NormalizedDocument(ref="doc.pdf", content=content, content_type=content_type)


def test_analyze_returns_result_from_poller(settings: IngestionSettings) -> None:
    expected = AnalyzeResult(api_version="2024-11-30", model_id=MODEL_ID, content="", pages=[])
    fake_sdk = _FakeSdkClient(_FakePoller(result_value=expected))
    client = AzureDocumentIntelligenceClient(settings, sdk_client=fake_sdk)  # type: ignore[arg-type]

    result = client.analyze(_document())

    assert result is expected


def test_analyze_calls_sdk_with_correct_arguments(settings: IngestionSettings) -> None:
    expected = AnalyzeResult(api_version="2024-11-30", model_id=MODEL_ID, content="", pages=[])
    fake_sdk = _FakeSdkClient(_FakePoller(result_value=expected))
    client = AzureDocumentIntelligenceClient(settings, sdk_client=fake_sdk)  # type: ignore[arg-type]

    client.analyze(_document(content=b"%PDF-body", content_type="application/pdf"))

    assert fake_sdk.calls == [
        {"model_id": MODEL_ID, "body": b"%PDF-body", "content_type": "application/pdf"}
    ]


def test_analyze_wraps_http_response_error(settings: IngestionSettings) -> None:
    fake_sdk = _FakeSdkClient(_FakePoller(error=HttpResponseError("service unavailable")))
    client = AzureDocumentIntelligenceClient(settings, sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(AzureServiceError):
        client.analyze(_document())


def test_analyze_wraps_service_request_error(settings: IngestionSettings) -> None:
    fake_sdk = _FakeSdkClient(_FakePoller(error=ServiceRequestError("connection failed")))
    client = AzureDocumentIntelligenceClient(settings, sdk_client=fake_sdk)  # type: ignore[arg-type]

    with pytest.raises(AzureServiceError):
        client.analyze(_document())


def test_constructs_real_sdk_client_when_none_injected(settings: IngestionSettings) -> None:
    client = AzureDocumentIntelligenceClient(settings)

    assert isinstance(client._sdk_client, AzureSdkClient)
