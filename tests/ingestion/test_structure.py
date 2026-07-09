from legal_rag.ingestion.models import (
    BoundingRegion,
    RawDocument,
    RawParagraph,
    RawParagraphRole,
    RawTable,
    RawTableCell,
)
from legal_rag.ingestion.structure import build_structure


def _region(page: int, y: float) -> BoundingRegion:
    return BoundingRegion(page_number=page, polygon=[0, y, 1, y, 1, y + 1, 0, y + 1])


def _paragraph(text: str, role: RawParagraphRole, page: int = 1, y: float = 0.0) -> RawParagraph:
    return RawParagraph(text=text, role=role, page_number=page, bounding_regions=[_region(page, y)])


def _table(page: int = 1, y: float = 0.0) -> RawTable:
    return RawTable(
        page_number=page,
        row_count=1,
        column_count=1,
        cells=[RawTableCell(row_index=0, column_index=0, text="cell")],
        bounding_regions=[_region(page, y)],
    )


def _document(
    paragraphs: list[RawParagraph] | None = None, tables: list[RawTable] | None = None
) -> RawDocument:
    return RawDocument(
        model_id="prebuilt-layout",
        api_version="2024-11-30",
        pages=[],
        paragraphs=paragraphs or [],
        tables=tables or [],
    )


def test_article_and_decimal_headings_nest_correctly() -> None:
    document = _document(
        paragraphs=[
            _paragraph("ARTICLE I — DEFINITIONS", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("1.1 Certain Definitions", RawParagraphRole.SECTION_HEADING, page=1, y=1),
            _paragraph('"Affiliate" means...', RawParagraphRole.TEXT, page=1, y=2),
        ]
    )

    result = build_structure(document)

    assert len(result.structure) == 1
    article = result.structure[0]
    assert article.section_id == "sec-1"
    assert article.level == 1
    assert len(article.children) == 1

    subsection = article.children[0]
    assert subsection.section_id == "sec-1-1"
    assert subsection.level == 2
    assert subsection.path == ["ARTICLE I — DEFINITIONS", "1.1 Certain Definitions"]
    assert subsection.content == ["heading-2", "para-3"]


def test_sibling_articles_close_previously_open_sections() -> None:
    document = _document(
        paragraphs=[
            _paragraph("ARTICLE I — DEFINITIONS", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("1.1 Certain Definitions", RawParagraphRole.SECTION_HEADING, page=1, y=1),
            _paragraph(
                "ARTICLE II — REPRESENTATIONS", RawParagraphRole.SECTION_HEADING, page=2, y=0
            ),
        ]
    )

    result = build_structure(document)

    assert len(result.structure) == 2
    assert result.structure[0].heading == "ARTICLE I — DEFINITIONS"
    assert result.structure[1].heading == "ARTICLE II — REPRESENTATIONS"
    assert result.structure[1].section_id == "sec-2"


def test_lettered_sub_item_nests_under_currently_open_section() -> None:
    document = _document(
        paragraphs=[
            _paragraph("1.1 Certain Definitions", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph(
                "(a) a Person that controls...", RawParagraphRole.SECTION_HEADING, page=1, y=1
            ),
        ]
    )

    result = build_structure(document)

    subsection = result.structure[0]
    assert len(subsection.children) == 1
    assert subsection.children[0].level == subsection.level + 1


def test_title_role_becomes_root_section_containing_preamble() -> None:
    document = _document(
        paragraphs=[
            _paragraph("MERGER AGREEMENT", RawParagraphRole.TITLE, page=1, y=0),
            _paragraph("THIS AGREEMENT is entered into...", RawParagraphRole.TEXT, page=1, y=1),
        ]
    )

    result = build_structure(document)

    assert len(result.structure) == 1
    assert result.structure[0].heading == "MERGER AGREEMENT"
    assert result.structure[0].content == ["heading-1", "para-2"]


def test_page_header_and_footer_are_excluded() -> None:
    document = _document(
        paragraphs=[
            _paragraph("Page 3 of 87", RawParagraphRole.PAGE_HEADER, page=1, y=0),
            _paragraph("Confidential", RawParagraphRole.PAGE_FOOTER, page=1, y=1),
            _paragraph("Body text.", RawParagraphRole.TEXT, page=1, y=2),
        ]
    )

    result = build_structure(document)

    assert len(result.elements) == 1
    assert result.elements[0].text == "Body text."


def test_footnote_preserved_as_ordinary_text_content() -> None:
    document = _document(
        paragraphs=[
            _paragraph("ARTICLE I", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("See footnote 1.", RawParagraphRole.FOOTNOTE, page=1, y=1),
        ]
    )

    result = build_structure(document)

    footnote_elements = [e for e in result.elements if e.type == "paragraph"]
    assert len(footnote_elements) == 1
    assert footnote_elements[0].text == "See footnote 1."
    assert result.structure[0].content == ["heading-1", "para-2"]


def test_content_before_any_heading_has_no_section_path() -> None:
    document = _document(
        paragraphs=[_paragraph("Preamble text.", RawParagraphRole.TEXT, page=1, y=0)]
    )

    result = build_structure(document)

    assert result.structure == []
    assert result.elements[0].section_path == []


def test_table_attached_to_currently_open_section_in_reading_order() -> None:
    document = _document(
        paragraphs=[
            _paragraph("ARTICLE III — REPS", RawParagraphRole.SECTION_HEADING, page=1, y=0),
        ],
        tables=[_table(page=1, y=1)],
    )

    result = build_structure(document)

    assert result.structure[0].content == ["heading-1", "table-2"]
    table_element = next(e for e in result.elements if e.type == "table")
    assert table_element.section_path == ["ARTICLE III — REPS"]
    assert table_element.row_count == 1
    assert table_element.cells[0].text == "cell"


def test_elements_ordered_by_page_then_vertical_position() -> None:
    document = _document(
        paragraphs=[
            _paragraph("second on page 1", RawParagraphRole.TEXT, page=1, y=5),
            _paragraph("first on page 1", RawParagraphRole.TEXT, page=1, y=0),
            _paragraph("first on page 2", RawParagraphRole.TEXT, page=2, y=0),
        ]
    )

    result = build_structure(document)

    assert [e.text for e in result.elements] == [
        "first on page 1",
        "second on page 1",
        "first on page 2",
    ]


def test_empty_document_produces_empty_structure_and_elements() -> None:
    result = build_structure(_document())

    assert result.structure == []
    assert result.elements == []
