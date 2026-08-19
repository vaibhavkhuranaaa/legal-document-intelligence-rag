"""Environment-driven configuration for the ingestion pipeline."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from legal_rag import __version__ as pipeline_version


class IngestionSettings(BaseSettings):
    """Typed settings loaded from the environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_document_intelligence_endpoint: str
    azure_document_intelligence_auth_mode: Literal["api_key", "managed_identity"] = "api_key"
    azure_document_intelligence_api_key: SecretStr | None = None

    input_dir: Path = Path("data/raw")
    output_dir: Path = Path("data/processed")
    failed_dir: Path = Path("data/failed")
    tmp_dir: Path = Path("data/tmp")
    logs_dir: Path = Path("logs/ingestion")
    storage_backend: Literal["local", "azure_blob"] = "local"
    azure_storage_account_url: str | None = None
    azure_storage_container: str | None = None
    azure_storage_source_prefix: str = "raw"
    azure_storage_processed_prefix: str = "processed"
    azure_storage_failed_prefix: str = "failed"
    azure_storage_reports_prefix: str = "manifests"

    max_retries: int = 3
    retry_backoff_seconds: float = 2.0

    pipeline_version: str = pipeline_version

    @model_validator(mode="after")
    def validate_production_settings(self) -> "IngestionSettings":
        if (
            self.azure_document_intelligence_auth_mode == "api_key"
            and self.azure_document_intelligence_api_key is None
        ):
            raise ValueError(
                "azure_document_intelligence_api_key is required when using API-key authentication"
            )
        if self.storage_backend == "azure_blob" and (
            not self.azure_storage_account_url or not self.azure_storage_container
        ):
            raise ValueError(
                "azure_storage_account_url and azure_storage_container are required "
                "for Azure Blob Storage"
            )
        return self


@lru_cache
def get_settings() -> IngestionSettings:
    """Return the process-wide settings singleton.

    Cached so settings are parsed once per process. Tests that need different
    settings should call `get_settings.cache_clear()` after patching the
    environment.
    """
    return IngestionSettings()
