"""Storage abstraction for the ingestion pipeline.

`StorageBackend` is the only interface `discovery.py` and `pipeline.py`'s
persistence stage depend on. `local.py` is the Phase 1 filesystem
implementation; a future `storage/blob.py` (Azure Blob Storage) can be added
as a second implementation with no change to any caller — see ADR-0005 in
`docs/decisions.md`.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class StorageBackend(ABC):
    """Read/write boundary for source documents and pipeline output."""

    @abstractmethod
    def list_source_documents(self) -> Iterator[str]:
        """Yield a ref for each available source document."""

    @abstractmethod
    def read_source_document(self, ref: str) -> bytes:
        """Read the raw bytes of a source document identified by `ref`."""

    @abstractmethod
    def write_processed_document(self, document_id: str, content: bytes) -> str:
        """Persist processed document bytes; return the location written to."""

    @abstractmethod
    def write_failure_record(self, document_id: str, content: bytes) -> str:
        """Persist a failure record's bytes; return the location written to."""
