from pathlib import Path

import pytest

from legal_rag.rag.source_registry import SourceRegistry


def test_registry_loads_committed_public_sources() -> None:
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))

    assert len(registry.documents) == 4
    document = registry.documents[0]
    assert document.source_url.startswith("https://")
    assert document.source_page_url(8).endswith("#page=8")
    assert registry.require(document.document_id) == document


def test_registry_rejects_unknown_document_id() -> None:
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))

    with pytest.raises(ValueError, match="no public source"):
        registry.require("0" * 64)


def test_page_link_requires_positive_page() -> None:
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))

    with pytest.raises(ValueError, match="positive"):
        registry.documents[0].source_page_url(0)
