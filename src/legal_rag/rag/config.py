"""Environment-driven configuration for the RAG layer.

Follows ADR-0008: configuration is parsed once, behind a single accessor;
no module reads the environment directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_openai_endpoint: str
    azure_openai_api_key: SecretStr
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str = "gpt-5-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    processed_dir: Path = Path("data/processed")
    dataset_manifest_path: Path = Path("data/dataset_manifest.json")
    chroma_persist_dir: Path = Path(".chroma")

    chunk_max_chars: int = 1800
    retrieval_top_k: int = 8
    answer_max_completion_tokens: int = 4000


@lru_cache
def get_rag_settings() -> RagSettings:
    """Return the process-wide RAG settings singleton (see `get_settings`)."""
    return RagSettings()
