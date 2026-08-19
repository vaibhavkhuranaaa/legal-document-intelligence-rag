from legal_rag.ingestion.sec_edgar import (
    SecEdgarClient,
    SecFilingInput,
    parse_edgar_html,
    to_sec_document_record,
)
from legal_rag.ingestion.validation import validate
from legal_rag.rag.chunking import chunk_document

_FILING = SecFilingInput(
    canonical_url="https://www.sec.gov/Archives/edgar/data/1/example.htm",
    cik="0000000001",
    accession_number="0000000001-24-000001",
    form_type="8-K",
    filing_date="2024-01-02",
    company_name="Example Company, Inc.",
    exhibit_identity="EX-2.1",
)


def test_native_html_parser_preserves_heading_anchor_table_and_malformed_tail() -> None:
    raw = parse_edgar_html(
        b"""<html><body><h1 id="article-one">ARTICLE I</h1><p>Merger terms.</p>
        <ul><li id="condition-a">Condition A</li></ul>
        <table id="consideration"><tr><th>Cash</th><th>Stock</th></tr>
        <tr><td>$10</td><td>0.2</td></tr></table>
        <p id="unterminated">Closing condition"""
    )

    assert raw.paragraphs[0].role == "sectionHeading"
    assert raw.paragraphs[0].source_anchor == "article-one"
    assert raw.paragraphs[-1].text == "Closing condition"
    assert raw.paragraphs[-1].source_start is not None
    assert raw.paragraphs[-1].source_end is not None
    assert raw.tables[0].row_count == 2
    assert raw.tables[0].cells[-1].text == "0.2"


def test_native_html_parser_applies_implied_block_closure() -> None:
    raw = parse_edgar_html(
        b'<p id="section">Section 1. Terms<p id="body">Ordinary agreement text.</p>'
    )

    assert [paragraph.text for paragraph in raw.paragraphs] == [
        "Section 1. Terms",
        "Ordinary agreement text.",
    ]
    assert raw.paragraphs[0].role == "sectionHeading"
    assert raw.paragraphs[1].role == "text"


def test_sec_record_is_chunkable_and_retains_immutable_filing_provenance() -> None:
    record = to_sec_document_record(
        filing=_FILING,
        content=b'<h1 id="article-one">ARTICLE I</h1><p>Merger terms.</p>',
        pipeline_version="test",
    )

    assert record.source.file_hash_sha256 == record.document_id
    assert record.source.sec_metadata is not None
    assert record.source.sec_metadata.accession_number == _FILING.accession_number
    chunks = chunk_document(record, title="Example merger agreement")
    assert chunks[0].source_anchor == "article-one"
    assert chunks[0].source_start is not None
    assert validate(record).is_valid is True


def test_sec_client_requires_a_declared_contact_identity() -> None:
    try:
        SecEdgarClient(user_agent="legal-rag")
    except ValueError as exc:
        assert "User-Agent" in str(exc)
    else:
        raise AssertionError("an undeclared SEC request identity must be rejected")
