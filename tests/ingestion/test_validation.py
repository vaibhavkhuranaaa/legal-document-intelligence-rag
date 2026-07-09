from datetime import UTC, datetime

from legal_rag.ingestion.models import (
    DocumentRecord,
    ExtractionInfo,
    ExtractionStatus,
    PageInfo,
    ParagraphElement,
    Section,
    SourceInfo,
)
from legal_rag.ingestion.validation import validate


def _valid_record() -> DocumentRecord:
    return DocumentRecord(
        document_id="abc123",
        source=SourceInfo(file_name="f.pdf", file_path="data/raw/f.pdf", file_hash_sha256="abc123"),
        extraction=ExtractionInfo(
            model_id="prebuilt-layout",
            api_version="2024-11-30",
            pipeline_version="1.0.0",
            extracted_at=datetime.now(UTC),
            status=ExtractionStatus.SUCCESS,
        ),
        page_count=1,
        pages=[PageInfo(page_number=1, width=8.5, height=11.0, unit="inch")],
        structure=[
            Section(
                section_id="sec-1",
                heading="ARTICLE I",
                level=1,
                page_number=1,
                path=["ARTICLE I"],
                content=["para-1"],
            )
        ],
        elements=[
            ParagraphElement(
                element_id="para-1", page_number=1, section_path=["ARTICLE I"], text="hello"
            )
        ],
    )


def test_valid_record_passes() -> None:
    result = validate(_valid_record())

    assert result.is_valid is True
    assert result.errors == []


def test_zero_page_count_is_rejected() -> None:
    record = _valid_record().model_copy(update={"page_count": 0, "pages": []})

    result = validate(record)

    assert result.is_valid is False
    assert any("page_count must be greater than 0" in error for error in result.errors)


def test_page_count_mismatch_is_rejected() -> None:
    record = _valid_record().model_copy(update={"page_count": 3})

    result = validate(record)

    assert result.is_valid is False
    assert any("does not match len(pages)" in error for error in result.errors)


def test_no_elements_is_rejected() -> None:
    record = _valid_record().model_copy(update={"elements": [], "structure": []})

    result = validate(record)

    assert result.is_valid is False
    assert any("no extracted elements" in error for error in result.errors)


def test_duplicate_element_ids_are_rejected() -> None:
    duplicate = ParagraphElement(element_id="para-1", page_number=1, section_path=[], text="x")
    record = _valid_record().model_copy(update={"elements": [duplicate, duplicate]})

    result = validate(record)

    assert result.is_valid is False
    assert any("duplicate element_id" in error for error in result.errors)


def test_out_of_range_page_number_is_rejected() -> None:
    out_of_range = ParagraphElement(
        element_id="para-1", page_number=5, section_path=[], text="hello"
    )
    record = _valid_record().model_copy(update={"elements": [out_of_range]})

    result = validate(record)

    assert result.is_valid is False
    assert any("out-of-range page_number" in error for error in result.errors)


def test_empty_text_is_rejected() -> None:
    empty = ParagraphElement(element_id="para-1", page_number=1, section_path=[], text="   ")
    record = _valid_record().model_copy(update={"elements": [empty]})

    result = validate(record)

    assert result.is_valid is False
    assert any("has empty text" in error for error in result.errors)


def test_section_referencing_unknown_element_id_is_rejected() -> None:
    section = Section(
        section_id="sec-1",
        heading="ARTICLE I",
        level=1,
        page_number=1,
        path=["ARTICLE I"],
        content=["para-999"],
    )
    record = _valid_record().model_copy(update={"structure": [section]})

    result = validate(record)

    assert result.is_valid is False
    assert any("references unknown element_id" in error for error in result.errors)


def test_nested_section_content_is_checked() -> None:
    child = Section(
        section_id="sec-1-1",
        heading="1.1",
        level=2,
        page_number=1,
        path=["ARTICLE I", "1.1"],
        content=["para-missing"],
    )
    parent = Section(
        section_id="sec-1",
        heading="ARTICLE I",
        level=1,
        page_number=1,
        path=["ARTICLE I"],
        children=[child],
    )
    record = _valid_record().model_copy(update={"structure": [parent]})

    result = validate(record)

    assert result.is_valid is False
    assert any("references unknown element_id" in error for error in result.errors)
