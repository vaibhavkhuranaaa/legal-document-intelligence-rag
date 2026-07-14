"""Environment-driven configuration for the RAG layer.

Follows ADR-0008: configuration is parsed once, behind a single accessor;
no module reads the environment directly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_openai_endpoint: str
    azure_openai_auth_mode: Literal["api_key", "managed_identity"] = "api_key"
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-5-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    processed_dir: Path = Path("data/processed")
    dataset_manifest_path: Path = Path("data/dataset_manifest.json")
    chroma_persist_dir: Path = Path(".chroma")
    retrieval_backend: Literal["chroma", "azure_ai_search"] = "chroma"
    azure_search_endpoint: str | None = None
    azure_search_index_name: str | None = None

    chunk_max_chars: int = 1800
    retrieval_top_k: int = 8
    answer_max_completion_tokens: int = 4000

    @model_validator(mode="after")
    def validate_production_settings(self) -> "RagSettings":
        if self.azure_openai_auth_mode == "api_key" and self.azure_openai_api_key is None:
            raise ValueError("azure_openai_api_key is required when using API-key authentication")
        if self.retrieval_backend == "azure_ai_search" and (
            not self.azure_search_endpoint or not self.azure_search_index_name
        ):
            raise ValueError(
                "azure_search_endpoint and azure_search_index_name are required "
                "for the Azure AI Search backend"
            )
        return self


@lru_cache
def get_rag_settings() -> RagSettings:
    """Return the process-wide RAG settings singleton (see `get_settings`)."""
    return RagSettings()
