from types import SimpleNamespace

import pytest

from legal_rag.ingestion.exceptions import StorageError
from legal_rag.ingestion.storage.blob import AzureBlobStorageBackend


class _FakeBlob:
    def __init__(self, store: dict[str, bytes], name: str) -> None:
        self._store = store
        self._name = name

    def download_blob(self):
        return SimpleNamespace(readall=lambda: self._store[self._name])

    def upload_blob(self, content: bytes, *, overwrite: bool) -> None:
        assert overwrite is True
        self._store[self._name] = content


class _FakeContainer:
    def __init__(self, store: dict[str, bytes]) -> None:
        self._store = store

    def list_blobs(self, *, name_starts_with: str):
        return [
            SimpleNamespace(name=name) for name in self._store if name.startswith(name_starts_with)
        ]

    def get_blob_client(self, name: str) -> _FakeBlob:
        return _FakeBlob(self._store, name)


class _FakeService:
    def __init__(self, store: dict[str, bytes]) -> None:
        self._container = _FakeContainer(store)

    def get_container_client(self, container: str) -> _FakeContainer:
        assert container == "legal-rag"
        return self._container


@pytest.fixture
def backend() -> AzureBlobStorageBackend:
    store = {"raw/b.pdf": b"b", "raw/a.pdf": b"a", "processed/old.json": b"old"}
    return AzureBlobStorageBackend(
        account_url="https://example.blob.core.windows.net",
        container="legal-rag",
        service_client=_FakeService(store),  # type: ignore[arg-type]
    )


def test_lists_and_reads_source_documents(backend: AzureBlobStorageBackend) -> None:
    assert list(backend.list_source_documents()) == ["a.pdf", "b.pdf"]
    assert backend.read_source_document("a.pdf") == b"a"


def test_writes_outputs_under_their_configured_prefixes(backend: AzureBlobStorageBackend) -> None:
    assert (
        backend.write_processed_document("doc", b"processed") == "az://legal-rag/processed/doc.json"
    )
    assert (
        backend.write_failure_record("failure", b"failed") == "az://legal-rag/failed/failure.json"
    )
    assert backend.write_run_report("run", b"report") == "az://legal-rag/manifests/run.json"


def test_rejects_blob_path_traversal(backend: AzureBlobStorageBackend) -> None:
    with pytest.raises(StorageError):
        backend.read_source_document("../private.pdf")
