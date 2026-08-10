"""Environment-driven configuration for the ingestion pipeline."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from legal_rag import __version__ as pipeline_version


class IngestionSettings(BaseSettings):
    """Typed settings loaded from the environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_document_intelligence_endpoint: str
    azure_document_intelligence_api_key: SecretStr

    input_dir: Path = Path("data/raw")
    output_dir: Path = Path("data/processed")
    failed_dir: Path = Path("data/failed")
    tmp_dir: Path = Path("data/tmp")
    logs_dir: Path = Path("logs/ingestion")

    max_retries: int = 3
    retry_backoff_seconds: float = 2.0

    pipeline_version: str = pipeline_version


@lru_cache
def get_settings() -> IngestionSettings:
    """Return the process-wide settings singleton.

    Cached so settings are parsed once per process. Tests that need different
    settings should call `get_settings.cache_clear()` after patching the
    environment.
    """
    return IngestionSettings()
