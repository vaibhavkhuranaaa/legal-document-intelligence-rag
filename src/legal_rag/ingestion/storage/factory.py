"""Construction point for the configured ingestion storage backend."""

from legal_rag.ingestion.config import IngestionSettings
from legal_rag.ingestion.storage.base import StorageBackend
from legal_rag.ingestion.storage.blob import AzureBlobStorageBackend
from legal_rag.ingestion.storage.local import LocalStorageBackend


def build_storage_backend(settings: IngestionSettings) -> StorageBackend:
    if settings.storage_backend == "azure_blob":
        if not settings.azure_storage_account_url or not settings.azure_storage_container:
            raise RuntimeError("Azure Blob Storage was selected without its required settings")
        return AzureBlobStorageBackend(
            account_url=settings.azure_storage_account_url,
            container=settings.azure_storage_container,
            source_prefix=settings.azure_storage_source_prefix,
            processed_prefix=settings.azure_storage_processed_prefix,
            failed_prefix=settings.azure_storage_failed_prefix,
            reports_prefix=settings.azure_storage_reports_prefix,
        )
    return LocalStorageBackend(
        input_dir=settings.input_dir,
        output_dir=settings.output_dir,
        failed_dir=settings.failed_dir,
        reports_dir=settings.logs_dir,
    )
