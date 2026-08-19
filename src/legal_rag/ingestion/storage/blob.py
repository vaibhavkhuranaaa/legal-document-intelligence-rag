"""Azure Blob Storage implementation for production ingestion artifacts."""

from collections.abc import Iterator
from pathlib import PurePosixPath

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from legal_rag.ingestion.exceptions import StorageError
from legal_rag.ingestion.storage.base import StorageBackend


class AzureBlobStorageBackend(StorageBackend):
    """Store corpus inputs and ingestion outputs in one Blob container.

    Containers are deliberately provisioned outside this class. The application
    only reads and writes under its configured prefixes and never creates cloud
    resources as an import-time or request-time side effect.
    """

    def __init__(
        self,
        *,
        account_url: str,
        container: str,
        source_prefix: str = "raw",
        processed_prefix: str = "processed",
        failed_prefix: str = "failed",
        reports_prefix: str = "manifests",
        service_client: BlobServiceClient | None = None,
    ) -> None:
        self._container = container
        self._source_prefix = source_prefix.strip("/")
        self._processed_prefix = processed_prefix.strip("/")
        self._failed_prefix = failed_prefix.strip("/")
        self._reports_prefix = reports_prefix.strip("/")
        self._service_client = service_client or BlobServiceClient(
            account_url=account_url, credential=DefaultAzureCredential()
        )
        self._container_client = self._service_client.get_container_client(container)

    def list_source_documents(self) -> Iterator[str]:
        prefix = f"{self._source_prefix}/"
        try:
            names = sorted(
                blob.name for blob in self._container_client.list_blobs(name_starts_with=prefix)
            )
        except AzureError as exc:
            raise StorageError("failed to list source documents") from exc
        for name in names:
            ref = name.removeprefix(prefix)
            if ref and not ref.endswith("/"):
                yield ref

    def read_source_document(self, ref: str) -> bytes:
        return self._read(self._source_prefix, ref)

    def write_processed_document(self, document_id: str, content: bytes) -> str:
        return self._write(self._processed_prefix, f"{document_id}.json", content)

    def write_failure_record(self, record_id: str, content: bytes) -> str:
        return self._write(self._failed_prefix, f"{record_id}.json", content)

    def write_run_report(self, run_id: str, content: bytes) -> str:
        return self._write(self._reports_prefix, f"{run_id}.json", content)

    def _read(self, prefix: str, ref: str) -> bytes:
        name = self._blob_name(prefix, ref)
        try:
            return self._container_client.get_blob_client(name).download_blob().readall()
        except AzureError as exc:
            raise StorageError("failed to read source document", context={"ref": ref}) from exc

    def _write(self, prefix: str, name: str, content: bytes) -> str:
        blob_name = self._blob_name(prefix, name)
        try:
            blob = self._container_client.get_blob_client(blob_name)
            blob.upload_blob(content, overwrite=True)
        except AzureError as exc:
            raise StorageError("failed to write blob", context={"path": blob_name}) from exc
        return f"az://{self._container}/{blob_name}"

    @staticmethod
    def _safe_ref(ref: str) -> str:
        path = PurePosixPath(ref)
        if not ref or path.is_absolute() or ".." in path.parts:
            raise StorageError("ref escapes the configured blob prefix", context={"ref": ref})
        return path.as_posix()

    def _blob_name(self, prefix: str, ref: str) -> str:
        return f"{prefix}/{self._safe_ref(ref)}"
