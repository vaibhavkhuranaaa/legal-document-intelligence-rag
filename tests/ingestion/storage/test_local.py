from pathlib import Path

import pytest

from legal_rag.ingestion.exceptions import StorageError
from legal_rag.ingestion.storage.local import LocalStorageBackend


@pytest.fixture
def backend(tmp_path: Path) -> LocalStorageBackend:
    return LocalStorageBackend(
        input_dir=tmp_path / "raw",
        output_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
    )


def test_list_source_documents_yields_files_sorted(backend: LocalStorageBackend) -> None:
    input_dir = backend._input_dir
    input_dir.mkdir(parents=True)
    (input_dir / "b.pdf").write_bytes(b"b")
    (input_dir / "a.pdf").write_bytes(b"a")
    (input_dir / "subdir").mkdir()

    assert list(backend.list_source_documents()) == ["a.pdf", "b.pdf"]


def test_list_source_documents_missing_dir_yields_nothing(backend: LocalStorageBackend) -> None:
    assert list(backend.list_source_documents()) == []


def test_read_source_document_returns_bytes(backend: LocalStorageBackend) -> None:
    input_dir = backend._input_dir
    input_dir.mkdir(parents=True)
    (input_dir / "doc.pdf").write_bytes(b"pdf-content")

    assert backend.read_source_document("doc.pdf") == b"pdf-content"


def test_read_source_document_missing_file_raises_storage_error(
    backend: LocalStorageBackend,
) -> None:
    backend._input_dir.mkdir(parents=True)

    with pytest.raises(StorageError):
        backend.read_source_document("missing.pdf")


def test_read_source_document_rejects_path_traversal(backend: LocalStorageBackend) -> None:
    backend._input_dir.mkdir(parents=True)

    with pytest.raises(StorageError):
        backend.read_source_document("../outside.pdf")


def test_write_processed_document_creates_dir_and_writes_content(
    backend: LocalStorageBackend,
) -> None:
    output_path = backend.write_processed_document("doc-1", b'{"schema_version": "1.0"}')

    written = Path(output_path)
    assert written.exists()
    assert written.read_bytes() == b'{"schema_version": "1.0"}'
    assert written.name == "doc-1.json"


def test_write_failure_record_creates_dir_and_writes_content(
    backend: LocalStorageBackend,
) -> None:
    output_path = backend.write_failure_record("doc-2", b'{"error": "corrupted"}')

    written = Path(output_path)
    assert written.exists()
    assert written.read_bytes() == b'{"error": "corrupted"}'
    assert written.parent == backend._failed_dir


def test_write_processed_document_leaves_no_tmp_file(backend: LocalStorageBackend) -> None:
    backend.write_processed_document("doc-3", b"content")

    tmp_files = list(backend._output_dir.glob("*.tmp"))
    assert tmp_files == []


def test_write_processed_document_overwrites_existing(backend: LocalStorageBackend) -> None:
    backend.write_processed_document("doc-4", b"first")
    output_path = backend.write_processed_document("doc-4", b"second")

    assert Path(output_path).read_bytes() == b"second"
