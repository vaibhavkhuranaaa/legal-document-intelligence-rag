import pytest
from azure.ai.documentintelligence.models import (
    AnalyzeResult,
    BoundingRegion,
    DocumentPage,
    DocumentParagraph,
    DocumentTable,
    DocumentTableCell,
)

from legal_rag.ingestion.adapter import to_raw_document
from legal_rag.ingestion.exceptions import ExtractionError
from legal_rag.ingestion.models import RawParagraphRole


def _page(page_number: int = 1, unit: str = "inch") -> DocumentPage:
    return DocumentPage(page_number=page_number, width=8.5, height=11.0, unit=unit, spans=[])


def _paragraph(
    text: str = "hello", role: str | None = None, page_number: int = 1
) -> DocumentParagraph:
    return DocumentParagraph(
        role=role,
        content=text,
        bounding_regions=[BoundingRegion(page_number=page_number, polygon=[0, 0, 1, 1])],
        spans=[],
    )


def _table(page_number: int = 1) -> DocumentTable:
    return DocumentTable(
        row_count=1,
        column_count=1,
        cells=[
            DocumentTableCell(
                row_index=0, column_index=0, content="cell", row_span=1, column_span=1, spans=[]
            )
        ],
        bounding_regions=[BoundingRegion(page_number=page_number, polygon=[])],
        spans=[],
    )


def _result(**overrides: object) -> AnalyzeResult:
    defaults: dict[str, object] = {
        "api_version": "2024-11-30",
        "model_id": "prebuilt-layout",
        "content": "",
        "pages": [_page()],
        "paragraphs": [_paragraph()],
        "tables": [],
    }
    defaults.update(overrides)
    return AnalyzeResult(**defaults)


def test_to_raw_document_maps_model_and_api_version() -> None:
    raw = to_raw_document(_result())

    assert raw.model_id == "prebuilt-layout"
    assert raw.api_version == "2024-11-30"


def test_to_raw_document_maps_pages() -> None:
    raw = to_raw_document(_result(pages=[_page(page_number=1), _page(page_number=2)]))

    assert [p.page_number for p in raw.pages] == [1, 2]
    assert raw.pages[0].unit == "inch"


@pytest.mark.parametrize(
    ("azure_role", "expected"),
    [
        ("title", RawParagraphRole.TITLE),
        ("sectionHeading", RawParagraphRole.SECTION_HEADING),
        ("pageHeader", RawParagraphRole.PAGE_HEADER),
        ("pageFooter", RawParagraphRole.PAGE_FOOTER),
        ("footnote", RawParagraphRole.FOOTNOTE),
        (None, RawParagraphRole.TEXT),
        ("pageNumber", RawParagraphRole.TEXT),  # unmapped role degrades to TEXT
    ],
)
def test_to_raw_document_maps_paragraph_roles(
    azure_role: str | None, expected: RawParagraphRole
) -> None:
    raw = to_raw_document(_result(paragraphs=[_paragraph(role=azure_role)]))

    assert raw.paragraphs[0].role == expected


def test_to_raw_document_maps_paragraph_text_and_page() -> None:
    raw = to_raw_document(_result(paragraphs=[_paragraph(text="ARTICLE I", page_number=3)]))

    assert raw.paragraphs[0].text == "ARTICLE I"
    assert raw.paragraphs[0].page_number == 3
    assert raw.paragraphs[0].bounding_regions[0].page_number == 3


def test_to_raw_document_maps_tables() -> None:
    raw = to_raw_document(_result(tables=[_table(page_number=2)]))

    assert len(raw.tables) == 1
    table = raw.tables[0]
    assert table.page_number == 2
    assert table.row_count == 1
    assert table.cells[0].text == "cell"


def test_paragraph_without_bounding_region_raises_extraction_error() -> None:
    paragraph = DocumentParagraph(role=None, content="orphan", bounding_regions=None, spans=[])

    with pytest.raises(ExtractionError):
        to_raw_document(_result(paragraphs=[paragraph]))


def test_table_without_bounding_region_raises_extraction_error() -> None:
    table = DocumentTable(
        row_count=1,
        column_count=1,
        cells=[
            DocumentTableCell(
                row_index=0, column_index=0, content="x", row_span=1, column_span=1, spans=[]
            )
        ],
        bounding_regions=None,
        spans=[],
    )

    with pytest.raises(ExtractionError):
        to_raw_document(_result(tables=[table]))


def test_to_raw_document_handles_no_paragraphs_or_tables() -> None:
    raw = to_raw_document(_result(paragraphs=None, tables=None))

    assert raw.paragraphs == []
    assert raw.tables == []
