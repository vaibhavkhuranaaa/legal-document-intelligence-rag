import pytest
from pydantic import ValidationError

from legal_rag.rag.config import RagSettings


def test_rag_settings_defaults() -> None:
    settings = RagSettings(
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="test-key",
    )

    assert settings.azure_openai_api_version == "2024-10-21"
    assert settings.azure_openai_chat_deployment == "gpt-5-mini"
    assert settings.azure_openai_embedding_deployment == "text-embedding-3-small"
    assert settings.chroma_persist_dir.name == ".chroma"


def test_azure_search_backend_requires_its_connection_settings() -> None:
    with pytest.raises(ValidationError, match="azure_search_endpoint"):
        RagSettings(
            azure_openai_endpoint="https://example.openai.azure.com/",
            azure_openai_api_key="test-key",
            retrieval_backend="azure_ai_search",
        )
