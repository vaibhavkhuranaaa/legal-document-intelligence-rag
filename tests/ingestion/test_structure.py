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


def test_bare_multi_char_roman_numeral_headings_are_siblings() -> None:
    """Unambiguous (2+ char) Roman numerals must not staircase into each other."""
    document = _document(
        paragraphs=[
            _paragraph("II. First", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("III. Second", RawParagraphRole.SECTION_HEADING, page=1, y=1),
            _paragraph("IV. Third", RawParagraphRole.SECTION_HEADING, page=1, y=2),
        ]
    )

    result = build_structure(document)

    assert len(result.structure) == 3
    assert [s.heading for s in result.structure] == ["II. First", "III. Second", "IV. Third"]
    assert all(s.level == 1 for s in result.structure)
    assert result.warnings == []


def test_bare_letter_headings_nest_as_new_level_under_roman_parent() -> None:
    """Bare letters (unambiguous, non-Roman-valid) must nest one level under
    an already-open Roman numeral, and stay flat siblings among themselves —
    not staircase, which was the original defect."""
    document = _document(
        paragraphs=[
            _paragraph("II. Background", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("A. First topic", RawParagraphRole.SECTION_HEADING, page=1, y=1),
            _paragraph("B. Second topic", RawParagraphRole.SECTION_HEADING, page=1, y=2),
            _paragraph("F. Third topic", RawParagraphRole.SECTION_HEADING, page=1, y=3),
        ]
    )

    result = build_structure(document)

    assert len(result.structure) == 1
    roman_section = result.structure[0]
    assert len(roman_section.children) == 3
    assert [c.heading for c in roman_section.children] == [
        "A. First topic",
        "B. Second topic",
        "F. Third topic",
    ]
    assert all(c.level == 2 for c in roman_section.children)
    assert result.warnings == []


def test_bare_lowercase_letter_headings_form_a_fourth_level() -> None:
    document = _document(
        paragraphs=[
            _paragraph("II. Background", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("A. Topic", RawParagraphRole.SECTION_HEADING, page=1, y=1),
            _paragraph("z. Detail one", RawParagraphRole.SECTION_HEADING, page=1, y=2),
            _paragraph("y. Detail two", RawParagraphRole.SECTION_HEADING, page=1, y=3),
        ]
    )

    result = build_structure(document)

    letter_section = result.structure[0].children[0]
    assert len(letter_section.children) == 2
    assert [c.heading for c in letter_section.children] == ["z. Detail one", "y. Detail two"]
    assert all(c.level == 3 for c in letter_section.children)


def test_ambiguous_heading_matching_multiple_open_depths_emits_warning() -> None:
    """A heading like 'C.' is textually valid as both a Roman numeral and a
    letter. When both interpretations match currently-open sections at
    *different* depths, this is genuine ambiguity: the shallowest matching
    depth is chosen (avoiding artificial over-nesting) and a structured
    warning is recorded — the heuristic never silently guesses here."""
    document = _document(
        paragraphs=[
            _paragraph("II. Intro", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("A. Sub", RawParagraphRole.SECTION_HEADING, page=1, y=1),
            _paragraph("C. Baz", RawParagraphRole.SECTION_HEADING, page=1, y=2),
        ]
    )

    result = build_structure(document)

    assert len(result.warnings) == 1
    assert "C. Baz" in result.warnings[0]
    assert "depths" in result.warnings[0]
    # Shallowest matching depth (the open Roman numeral, depth 1) wins.
    assert len(result.structure) == 2
    assert result.structure[1].heading == "C. Baz"
    assert result.structure[1].level == 1


def test_single_character_ambiguous_heading_can_be_reclaimed_by_a_later_sibling() -> None:
    """Documents this heuristic's known residual limitation: a single
    character valid as both a Roman numeral and a letter (I, V, X, L, C, D,
    M) opens ambiguously. If the very next heading is an unambiguous letter,
    it matches the ambiguous entry's letter interpretation and replaces it
    at the *same* depth, rather than opening beneath it. This is a
    deterministic, documented consequence of resolving genuine textual
    ambiguity by matching against open styles — not a random guess — but it
    means a lone Roman-numeral-style opener whose numeral is also a valid
    letter (most commonly "I.") can be "reclaimed" as a letter-list sibling
    instead of remaining a Roman-numeral parent, if nothing yet
    distinguishes it. Using a multi-character Roman numeral (e.g. "II.")
    avoids this ambiguity entirely, as covered by the tests above."""
    document = _document(
        paragraphs=[
            _paragraph("I. Intro", RawParagraphRole.SECTION_HEADING, page=1, y=0),
            _paragraph("A. Sub", RawParagraphRole.SECTION_HEADING, page=1, y=1),
        ]
    )

    result = build_structure(document)

    assert len(result.structure) == 2
    assert [s.heading for s in result.structure] == ["I. Intro", "A. Sub"]
    assert all(s.level == 1 for s in result.structure)


def test_real_abraham_opinion_heading_sequence_no_longer_staircases() -> None:
    """Regression test using the real heading sequence from the Abraham v.
    Estate of Wirtz opinion (C.A. No. 2023-0865-BWD) that originally exposed
    this heuristic's staircase defect during Phase 1.5 live validation. This
    locks in the verified, improved behavior — not an idealized one."""
    headings = [
        "IN THE COURT OF CHANCERY OF THE STATE OF DELAWARE",
        "MEMORANDUM OPINION RESOLVING MOTION TO DISMISS",
        "I. BACKGROUND1",
        "A. AM's Assets And Ownership Structure",
        "B. The Merger Certificate",
        "C. The Notice",
        "D. Plaintiff Demands Appraisal.",
        "E. Procedural History",
        "II. ANALYSIS",
    ]
    document = _document(
        paragraphs=[
            _paragraph(text, RawParagraphRole.SECTION_HEADING, page=1, y=i)
            for i, text in enumerate(headings)
        ]
    )

    result = build_structure(document)

    # "I." and the five lettered subsections (A-E) are all flat siblings,
    # not an 8-level staircase (the originally observed defect) — this is
    # the primary, verified improvement from this enhancement. Popping a
    # section off the open-sections stack (when a later heading reuses its
    # depth) only affects future matching, not its already-fixed position
    # in the tree, so "I." correctly remains alongside A-E here.
    root = result.structure[0].children[0]  # MEMORANDUM OPINION
    assert [c.heading for c in root.children] == [
        "I. BACKGROUND1",
        "A. AM's Assets And Ownership Structure",
        "B. The Merger Certificate",
        "C. The Notice",
        "D. Plaintiff Demands Appraisal.",
        "E. Procedural History",
    ]
    assert len({c.level for c in root.children}) == 1  # all at the same depth
