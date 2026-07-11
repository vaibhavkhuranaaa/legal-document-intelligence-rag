from datetime import UTC, datetime

from legal_rag.ingestion.models import (
    DocumentRecord,
    Element,
    ExtractionInfo,
    ExtractionStatus,
    PageInfo,
    ParagraphElement,
    SourceInfo,
    TableCell,
    TableElement,
)
from legal_rag.rag.chunking import chunk_document


def _record(elements: list[Element], page_count: int = 3) -> DocumentRecord:
    return DocumentRecord(
        document_id="deadbeef" * 8,
        source=SourceInfo(file_name="f.pdf", file_path="f.pdf", file_hash_sha256="deadbeef" * 8),
        extraction=ExtractionInfo(
            model_id="prebuilt-layout",
            api_version="2024-11-30",
            pipeline_version="0.1.0",
            extracted_at=datetime.now(UTC),
            status=ExtractionStatus.SUCCESS,
        ),
        page_count=page_count,
        pages=[
            PageInfo(page_number=n, width=8.5, height=11.0, unit="inch")
            for n in range(1, page_count + 1)
        ],
        structure=[],
        elements=elements,
    )


def _para(element_id: str, text: str, page: int = 1, path: list[str] | None = None):
    return ParagraphElement(
        element_id=element_id, page_number=page, section_path=path or [], text=text
    )


def test_paragraphs_in_same_section_group_into_one_chunk() -> None:
    record = _record(
        [
            _para("p1", "First paragraph.", path=["I. INTRO"]),
            _para("p2", "Second paragraph.", path=["I. INTRO"]),
        ]
    )

    chunks = chunk_document(record, title="Case A")

    assert len(chunks) == 1
    assert chunks[0].text == "First paragraph.\n\nSecond paragraph."
    assert chunks[0].element_ids == ["p1", "p2"]
    assert chunks[0].section_path == ["I. INTRO"]


def test_section_change_starts_a_new_chunk() -> None:
    record = _record(
        [
            _para("p1", "Intro text.", path=["I. INTRO"]),
            _para("p2", "Analysis text.", path=["II. ANALYSIS"]),
        ]
    )

    chunks = chunk_document(record, title="Case A")

    assert len(chunks) == 2
    assert chunks[0].section_path == ["I. INTRO"]
    assert chunks[1].section_path == ["II. ANALYSIS"]


def test_max_chars_splits_at_paragraph_boundary() -> None:
    long_text = "x" * 900
    record = _record(
        [
            _para("p1", long_text, path=["I"]),
            _para("p2", long_text, path=["I"]),
            _para("p3", long_text, path=["I"]),
        ]
    )

    chunks = chunk_document(record, title="Case A", max_chars=1800)

    assert len(chunks) == 2
    assert chunks[0].element_ids == ["p1", "p2"]
    assert chunks[1].element_ids == ["p3"]


def test_footnote_markers_are_dropped() -> None:
    record = _record(
        [
            _para("p1", "Real content.", path=["I"]),
            _para("p2", "14", path=["I"]),
            _para("p3", "32.", path=["I"]),
        ]
    )

    chunks = chunk_document(record, title="Case A")

    assert len(chunks) == 1
    assert chunks[0].text == "Real content."
    assert chunks[0].element_ids == ["p1"]


def test_table_becomes_atomic_chunk() -> None:
    table = TableElement(
        element_id="t1",
        page_number=2,
        section_path=["III. VALUATION"],
        row_count=2,
        column_count=2,
        cells=[
            TableCell(row_index=0, column_index=0, text="Metric"),
            TableCell(row_index=0, column_index=1, text="Value"),
            TableCell(row_index=1, column_index=0, text="Deal price"),
            TableCell(row_index=1, column_index=1, text="$15.00"),
        ],
    )
    record = _record([_para("p1", "Before table.", path=["III. VALUATION"]), table])

    chunks = chunk_document(record, title="Case A")

    assert len(chunks) == 2
    assert chunks[1].chunk_type == "table"
    assert "Deal price | $15.00" in chunks[1].text
    assert chunks[1].page_start == chunks[1].page_end == 2


def test_embed_text_carries_title_and_section_path() -> None:
    record = _record([_para("p1", "The court finds.", path=["II. ANALYSIS", "A. Standard"])])

    chunks = chunk_document(record, title="Dell v. Magnetar (2017)")

    assert chunks[0].embed_text.startswith("Dell v. Magnetar (2017) › II. ANALYSIS › A. Standard")
    assert chunks[0].text == "The court finds."


def test_page_range_spans_grouped_paragraphs() -> None:
    record = _record(
        [
            _para("p1", "Starts on page one.", page=1, path=["I"]),
            _para("p2", "Continues on page two.", page=2, path=["I"]),
        ]
    )

    chunks = chunk_document(record, title="Case A")

    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
