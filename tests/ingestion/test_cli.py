import logging
from pathlib import Path

import pytest

from legal_rag.ingestion.cli import main
from legal_rag.ingestion.config import get_settings


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    get_settings.cache_clear()
    namespace_logger = logging.getLogger("legal_rag")
    namespace_logger.handlers.clear()
    namespace_logger.propagate = True
    yield
    get_settings.cache_clear()
    namespace_logger.handlers.clear()
    namespace_logger.propagate = True


@pytest.fixture
def configured_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
        "https://example.cognitiveservices.azure.com/",
    )
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", "dummy-key")
    monkeypatch.setenv("INPUT_DIR", str(tmp_path / "raw"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "processed"))
    monkeypatch.setenv("FAILED_DIR", str(tmp_path / "failed"))
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    return tmp_path


def test_main_returns_zero_on_empty_run(
    configured_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main()

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "0 document(s) processed" in captured.out
    report_files = list((configured_env / "logs").glob("*.json"))
    assert len(report_files) == 1


def test_main_returns_one_when_settings_are_invalid(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_DOCUMENT_INTELLIGENCE_API_KEY", raising=False)

    exit_code = main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "failed to complete" in captured.err
