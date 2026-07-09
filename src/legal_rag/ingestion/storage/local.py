"""Filesystem-backed `StorageBackend` implementation, used in local development."""

from collections.abc import Iterator
from pathlib import Path

from legal_rag.ingestion.exceptions import StorageError
from legal_rag.ingestion.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    def __init__(
        self, *, input_dir: Path, output_dir: Path, failed_dir: Path, reports_dir: Path
    ) -> None:
        self._input_dir = input_dir
        self._output_dir = output_dir
        self._failed_dir = failed_dir
        self._reports_dir = reports_dir

    def list_source_documents(self) -> Iterator[str]:
        if not self._input_dir.exists():
            return
        for path in sorted(self._input_dir.iterdir()):
            if path.is_file():
                yield path.name

    def read_source_document(self, ref: str) -> bytes:
        path = self._resolve_input_path(ref)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError(
                f"failed to read source document: {ref}", context={"ref": ref}
            ) from exc

    def write_processed_document(self, document_id: str, content: bytes) -> str:
        return self._atomic_write(self._output_dir, f"{document_id}.json", content)

    def write_failure_record(self, record_id: str, content: bytes) -> str:
        return self._atomic_write(self._failed_dir, f"{record_id}.json", content)

    def write_run_report(self, run_id: str, content: bytes) -> str:
        return self._atomic_write(self._reports_dir, f"{run_id}.json", content)

    def _resolve_input_path(self, ref: str) -> Path:
        resolved_input_dir = self._input_dir.resolve()
        path = (self._input_dir / ref).resolve()
        if not path.is_relative_to(resolved_input_dir):
            raise StorageError("ref escapes the input directory", context={"ref": ref})
        return path

    def _atomic_write(self, directory: Path, file_name: str, content: bytes) -> str:
        directory.mkdir(parents=True, exist_ok=True)
        final_path = directory / file_name
        tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
        try:
            tmp_path.write_bytes(content)
            tmp_path.replace(final_path)
        except OSError as exc:
            raise StorageError(
                f"failed to write {file_name}", context={"path": str(final_path)}
            ) from exc
        finally:
            tmp_path.unlink(missing_ok=True)
        return str(final_path)
