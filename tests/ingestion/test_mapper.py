import hashlib
from datetime import UTC, datetime

from legal_rag.ingestion.mapper import SourceFileInfo, compute_document_id, to_document_record
from legal_rag.ingestion.models import (
    ExtractionStatus,
    ParagraphElement,
    RawDocument,
    RawPage,
    SecMetadata,
    Section,
)
from legal_rag.ingestion.structure import DocumentStructure


def test_compute_document_id_matches_sha256_hexdigest() -> None:
    content = b"some document bytes"

    assert compute_document_id(content) == hashlib.sha256(content).hexdigest()


def test_compute_document_id_is_deterministic() -> None:
    content = b"some document bytes"

    assert compute_document_id(content) == compute_document_id(content)


def _raw_document() -> RawDocument:
    return RawDocument(
        model_id="prebuilt-layout",
        api_version="2024-11-30",
        pages=[
            RawPage(page_number=1, width=8.5, height=11.0, unit="inch"),
            RawPage(page_number=2, width=8.5, height=11.0, unit="inch"),
        ],
        paragraphs=[],
        tables=[],
    )


def _structure() -> DocumentStructure:
    section = Section(
        section_id="sec-1", heading="ARTICLE I", level=1, page_number=1, path=["ARTICLE I"]
    )
    element = ParagraphElement(
        element_id="para-1", page_number=1, section_path=["ARTICLE I"], text="hello"
    )
    return DocumentStructure(structure=[section], elements=[element])


def test_to_document_record_assembles_fields() -> None:
    content = b"%PDF-fake-content"
    extracted_at = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    structure = _structure()

    record = to_document_record(
        document_structure=structure,
        raw_document=_raw_document(),
        source=SourceFileInfo(
            file_name="merger.pdf", file_path="data/raw/merger.pdf", content=content
        ),
        pipeline_version="1.0.0",
        extracted_at=extracted_at,
        extraction_status=ExtractionStatus.SUCCESS,
    )

    expected_hash = hashlib.sha256(content).hexdigest()
    assert record.document_id == expected_hash
    assert record.source.file_hash_sha256 == expected_hash
    assert record.source.file_name == "merger.pdf"
    assert record.source.file_path == "data/raw/merger.pdf"
    assert record.source.sec_metadata is None
    assert record.extraction.model_id == "prebuilt-layout"
    assert record.extraction.api_version == "2024-11-30"
    assert record.extraction.pipeline_version == "1.0.0"
    assert record.extraction.extracted_at == extracted_at
    assert record.extraction.status == ExtractionStatus.SUCCESS
    assert record.extraction.warnings == []
    assert record.page_count == 2
    assert [p.page_number for p in record.pages] == [1, 2]
    assert record.structure == structure.structure
    assert record.elements == structure.elements


def test_to_document_record_includes_sec_metadata_when_provided() -> None:
    sec_metadata = SecMetadata(cik="0001234567", form_type="S-4", company_name="Acme Corp")

    record = to_document_record(
        document_structure=_structure(),
        raw_document=_raw_document(),
        source=SourceFileInfo(
            file_name="merger.pdf",
            file_path="data/raw/merger.pdf",
            content=b"content",
            sec_metadata=sec_metadata,
        ),
        pipeline_version="1.0.0",
        extracted_at=datetime(2026, 7, 9, tzinfo=UTC),
        extraction_status=ExtractionStatus.SUCCESS,
    )

    assert record.source.sec_metadata == sec_metadata


def test_to_document_record_preserves_explicit_warnings() -> None:
    record = to_document_record(
        document_structure=_structure(),
        raw_document=_raw_document(),
        source=SourceFileInfo(
            file_name="merger.pdf", file_path="data/raw/merger.pdf", content=b"content"
        ),
        pipeline_version="1.0.0",
        extracted_at=datetime(2026, 7, 9, tzinfo=UTC),
        extraction_status=ExtractionStatus.PARTIAL,
        warnings=["low_confidence_page_2"],
    )

    assert record.extraction.status == ExtractionStatus.PARTIAL
    assert record.extraction.warnings == ["low_confidence_page_2"]
