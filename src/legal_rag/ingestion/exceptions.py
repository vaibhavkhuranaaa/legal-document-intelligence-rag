"""Typed exceptions for the ingestion pipeline.

Every exception carries an optional `context` mapping so the orchestrator
(`pipeline.py`) can log structured error details and populate a document's
`ManifestEntry` without re-deriving what went wrong. Exceptions are grouped
into four categories so `pipeline.py` can decide how to react to a failure
(retry, skip and record, or abort the run) based on its category rather than
its specific type:

- `UserInputError`: the source document itself is the problem (bad format,
  corrupted file). Not retryable; always the document's fault.
- `InfrastructureError`: a dependency (Azure, storage) failed. May be
  transient and retryable depending on the specific error.
- `ExtractionError`: Azure returned successfully but the result could not be
  turned into a usable structured document.
- `ValidationFailedError`: a constructed `DocumentRecord` failed schema or
  semantic validation before being persisted.
"""

from typing import Any


class IngestionError(Exception):
    """Base class for all ingestion pipeline errors."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class UserInputError(IngestionError):
    """The source document is invalid, independent of any external service."""


class UnsupportedFormatError(UserInputError):
    """The source document's format is not supported by the pipeline."""


class CorruptedDocumentError(UserInputError):
    """The source document could not be read or parsed as a valid file."""


class InfrastructureError(IngestionError):
    """A dependency (Azure Document Intelligence, storage) failed."""


class AzureServiceError(InfrastructureError):
    """The Azure Document Intelligence call failed or exhausted its retries."""


class StorageError(InfrastructureError):
    """A read or write against the storage backend failed."""


class ExtractionError(IngestionError):
    """Azure returned a result, but it could not be turned into structured content."""


class ValidationFailedError(IngestionError):
    """A constructed `DocumentRecord` failed validation before persistence."""


class SchemaValidationError(ValidationFailedError):
    """The document failed to conform to the `DocumentRecord` schema."""


class SemanticValidationError(ValidationFailedError):
    """The document is schema-valid but fails a business-level sanity check."""
