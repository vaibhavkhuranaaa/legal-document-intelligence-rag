"""Thin wrapper around the Azure Document Intelligence SDK.

This is the second (and last) module permitted to import
`azure.ai.documentintelligence` types — see `adapter.py` and ADR-0004. It
owns authentication, request submission/polling, and translating SDK-level
failures into `AzureServiceError`. Its result is handed directly to
`adapter.to_raw_document()`, so nothing past this module ever sees the SDK's
response shape.

Retry/backoff for transient failures is delegated to azure-core's built-in
retry policy (configured from `IngestionSettings`) rather than hand-rolled —
it already implements exponential backoff correctly, and always retries 429
responses (which carry a `Retry-After` header) regardless of HTTP method.
5xx errors on the initial submission (a POST) are deliberately not retried by
azure-core's default method allowlist; this is the safer default for a paid,
non-idempotent operation, and the subsequent status-polling requests (GET)
are retried normally.
"""

from azure.ai.documentintelligence import DocumentIntelligenceClient as _AzureSdkClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError, ServiceResponseError

from legal_rag.ingestion.config import IngestionSettings
from legal_rag.ingestion.exceptions import AzureServiceError
from legal_rag.ingestion.normalization import NormalizedDocument

MODEL_ID = "prebuilt-layout"


class AzureDocumentIntelligenceClient:
    """Submits normalized documents to Azure Document Intelligence."""

    def __init__(
        self, settings: IngestionSettings, *, sdk_client: _AzureSdkClient | None = None
    ) -> None:
        self._sdk_client = sdk_client or _AzureSdkClient(
            endpoint=settings.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(
                settings.azure_document_intelligence_api_key.get_secret_value()
            ),
            retry_total=settings.max_retries,
            retry_backoff_factor=settings.retry_backoff_seconds,
        )

    def analyze(self, document: NormalizedDocument) -> AnalyzeResult:
        """Submit a document for analysis and block until the result is ready."""
        try:
            poller = self._sdk_client.begin_analyze_document(
                MODEL_ID,
                body=document.content,
                content_type=document.content_type,
            )
            return poller.result()
        except (HttpResponseError, ServiceRequestError, ServiceResponseError) as exc:
            raise AzureServiceError(
                f"Azure Document Intelligence request failed for {document.ref!r}: {exc}",
                context={"ref": document.ref, "model_id": MODEL_ID},
            ) from exc
