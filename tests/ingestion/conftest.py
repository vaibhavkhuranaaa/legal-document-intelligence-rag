"""Shared fixtures for ingestion tests."""

from collections.abc import Iterator

import pytest

from legal_rag.ingestion.storage.base import StorageBackend


class FakeStorageBackend(StorageBackend):
    """In-memory `StorageBackend` test double."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self._files = dict(files or {})
        self.written_processed: dict[str, bytes] = {}
        self.written_failed: dict[str, bytes] = {}

    def list_source_documents(self) -> Iterator[str]:
        yield from self._files

    def read_source_document(self, ref: str) -> bytes:
        return self._files[ref]

    def write_processed_document(self, document_id: str, content: bytes) -> str:
        self.written_processed[document_id] = content
        return f"processed/{document_id}.json"

    def write_failure_record(self, document_id: str, content: bytes) -> str:
        self.written_failed[document_id] = content
        return f"failed/{document_id}.json"


@pytest.fixture
def fake_storage() -> FakeStorageBackend:
    return FakeStorageBackend()
