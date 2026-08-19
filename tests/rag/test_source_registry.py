import json
from pathlib import Path

import pytest

from legal_rag.rag import source_registry
from legal_rag.rag.source_registry import CorpusDocument, SourceRegistry


def test_registry_loads_committed_public_sources() -> None:
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))

    assert len(registry.documents) == 20
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


def test_registry_supports_sec_html_without_making_a_page_claim(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "sha256": "a" * 64,
                        "local_filename": "example.html",
                        "display_name": "Example merger agreement",
                        "case_name": "Example merger agreement",
                        "docket_number": "0000000001-24-000001",
                        "court": "SEC EDGAR",
                        "jurisdiction": "United States",
                        "year": 2024,
                        "legal_topic": "merger agreement",
                        "source_kind": "sec_html",
                        "source_url": "https://www.sec.gov/Archives/edgar/data/1/example.htm",
                        "company_name": "Example Company",
                        "form_type": "8-K",
                        "accession_number": "0000000001-24-000001",
                        "filing_date": "2024-01-02",
                        "exhibit_identity": "EX-2.1",
                    }
                ]
            }
        )
    )

    document = SourceRegistry.load(manifest).documents[0]

    assert document.source_section_url("article-one").endswith("#article-one")
    assert document.source_link_label == "Open official filing"
    with pytest.raises(ValueError, match="stable PDF pages"):
        document.source_page_url(1)


def test_sec_url_verification_requires_declared_contact_identity() -> None:
    registry = SourceRegistry([_sec_document()])

    with pytest.raises(ValueError, match="declared SEC User-Agent"):
        registry.verify_source_urls()


def test_sec_url_verification_uses_contact_identity_and_ranged_get(monkeypatch) -> None:
    requests = []

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def _urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response()

    monkeypatch.setattr(source_registry, "urlopen", _urlopen)
    SourceRegistry([_sec_document()]).verify_source_urls(
        sec_user_agent="Legal RAG contact@example.com"
    )

    request, timeout = requests[0]
    assert request.get_method() == "GET"
    assert request.get_header("User-agent") == "Legal RAG contact@example.com"
    assert request.get_header("Range") == "bytes=0-0"
    assert timeout == 15.0


def _sec_document() -> CorpusDocument:
    return CorpusDocument(
        document_id="a" * 64,
        local_filename="example.html",
        display_name="Example merger agreement",
        case_name="Example merger agreement",
        docket_number="0000000001-24-000001",
        court="SEC EDGAR",
        jurisdiction="United States",
        year=2024,
        legal_topic="merger agreement",
        source_kind="sec_html",
        source_url="https://www.sec.gov/Archives/edgar/data/1/example.htm",
        company_name="Example Company",
        form_type="8-K",
        accession_number="0000000001-24-000001",
        filing_date="2024-01-02",
        exhibit_identity="EX-2.1",
    )
