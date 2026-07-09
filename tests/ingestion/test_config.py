from pathlib import Path

import pytest
from pydantic import ValidationError

from legal_rag.ingestion.config import IngestionSettings, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        "https://example.cognitiveservices.azure.com/",
    )
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", "dummy-key")


def test_settings_load_from_env(required_env: None) -> None:
    settings = get_settings()

    assert settings.azure_document_intelligence_endpoint == (
        "https://example.cognitiveservices.azure.com/"
    )
    assert settings.azure_document_intelligence_api_key.get_secret_value() == "dummy-key"


def test_settings_defaults(required_env: None) -> None:
    settings = get_settings()

    assert settings.input_dir == Path("data/raw")
    assert settings.output_dir == Path("data/processed")
    assert settings.failed_dir == Path("data/failed")
    assert settings.tmp_dir == Path("data/tmp")
    assert settings.logs_dir == Path("logs/ingestion")
    assert settings.max_retries == 3
    assert settings.pipeline_version


def test_settings_missing_required_fields_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        IngestionSettings(_env_file=None)  # type: ignore[call-arg]
