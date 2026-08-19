from legal_rag.ingestion.storage.base import StorageBackend
from legal_rag.ingestion.storage.blob import AzureBlobStorageBackend
from legal_rag.ingestion.storage.factory import build_storage_backend
from legal_rag.ingestion.storage.local import LocalStorageBackend

__all__ = [
    "AzureBlobStorageBackend",
    "LocalStorageBackend",
    "StorageBackend",
    "build_storage_backend",
]
