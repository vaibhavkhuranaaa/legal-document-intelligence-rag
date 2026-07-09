"""Reconstructs a section hierarchy from Azure's flat paragraph/table stream.

Azure Document Intelligence's `prebuilt-layout` model does not return a
heading hierarchy — every heading paragraph is tagged either `title` or
`sectionHeading`, with no depth information. This module infers depth from
the heading text's own numbering convention (e.g. "ARTICLE I", "1.1",
"(a)"), which is how M&A legal documents are actually structured. This is a
heuristic, not a guarantee, as noted in the approved Phase 1 design (Section
3: Azure Document Intelligence limitations).

`page_header` / `page_footer` paragraphs (running boilerplate, e.g. "Page 3
of 87") are excluded entirely — they are not body content. `footnote`
paragraphs are preserved as ordinary text content; the schema does not have
a distinct footnote element type.

Reading order across pages is unambiguous (page number), but within a page,
paragraphs and tables are two separate lists with no shared ordering key in
`RawDocument`. This module orders same-page elements by the vertical
position (topmost y-coordinate) of each element's first bounding region —
accurate for the common single-column legal document layout, but a known
limitation for multi-column layouts.
"""

import re
from dataclasses import dataclass

from legal_rag.ingestion.models import (
    BoundingRegion,
    Element,
    HeadingElement,
    ParagraphElement,
    RawDocument,
    RawParagraph,
    RawParagraphRole,
    RawTable,
    Section,
    TableCell,
    TableElement,
)

_EXCLUDED_ROLES = frozenset({RawParagraphRole.PAGE_HEADER, RawParagraphRole.PAGE_FOOTER})
_HEADING_ROLES = frozenset({RawParagraphRole.TITLE, RawParagraphRole.SECTION_HEADING})

_ARTICLE_PATTERN = re.compile(r"^ARTICLE\s+", re.IGNORECASE)
_DECIMAL_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")
_SUB_ITEM_PATTERN = re.compile(r"^\(?[a-zA-Z]\)|^\(?[ivxlcdm]+\)", re.IGNORECASE)


@dataclass(frozen=True)
class DocumentStructure:
    structure: list[Section]
    elements: list[Element]


@dataclass
class _ReadingOrderItem:
    page_number: int
    vertical_position: float
    paragraph: RawParagraph | None = None
    table: RawTable | None = None


@dataclass
class _OpenSection:
    section: Section
    depth: int


def _min_y(regions: list[BoundingRegion]) -> float:
    if not regions or not regions[0].polygon:
        return 0.0
    return min(regions[0].polygon[1::2])


def _infer_heading_depth(text: str, *, current_open_depth: int) -> int:
    """Infer a heading's nesting depth from its own numbering convention."""
    stripped = text.strip()

    if _ARTICLE_PATTERN.match(stripped):
        return 1

    decimal_match = _DECIMAL_PATTERN.match(stripped)
    if decimal_match:
        return decimal_match.group(1).count(".") + 1

    if _SUB_ITEM_PATTERN.match(stripped):
        return current_open_depth + 1 if current_open_depth else 1

    return current_open_depth + 1 if current_open_depth else 1


def _build_reading_order(document: RawDocument) -> list[_ReadingOrderItem]:
    items = [
        _ReadingOrderItem(
            page_number=paragraph.page_number,
            vertical_position=_min_y(paragraph.bounding_regions),
            paragraph=paragraph,
        )
        for paragraph in document.paragraphs
        if paragraph.role not in _EXCLUDED_ROLES
    ]
    items.extend(
        _ReadingOrderItem(
            page_number=table.page_number,
            vertical_position=_min_y(table.bounding_regions),
            table=table,
        )
        for table in document.tables
    )
    items.sort(key=lambda item: (item.page_number, item.vertical_position))
    return items


def _open_section(
    *,
    stack: list[_OpenSection],
    structure: list[Section],
    heading_text: str,
    depth: int,
    page_number: int,
) -> Section:
    while stack and stack[-1].depth >= depth:
        stack.pop()

    parent = stack[-1].section if stack else None
    index = len(parent.children) if parent else len(structure)
    section_id = f"{parent.section_id}-{index + 1}" if parent else f"sec-{index + 1}"
    path = [*parent.path, heading_text] if parent else [heading_text]

    section = Section(
        section_id=section_id,
        heading=heading_text,
        level=depth,
        page_number=page_number,
        path=path,
    )
    if parent:
        parent.children.append(section)
    else:
        structure.append(section)
    stack.append(_OpenSection(section=section, depth=depth))
    return section


def build_structure(document: RawDocument) -> DocumentStructure:
    structure: list[Section] = []
    elements: list[Element] = []
    stack: list[_OpenSection] = []
    next_element_id = 1

    for item in _build_reading_order(document):
        section_path = stack[-1].section.path if stack else []

        if item.paragraph is not None:
            paragraph = item.paragraph
            element_id = (
                f"heading-{next_element_id}"
                if paragraph.role in _HEADING_ROLES
                else f"para-{next_element_id}"
            )
            next_element_id += 1

            if paragraph.role in _HEADING_ROLES:
                depth = _infer_heading_depth(
                    paragraph.text, current_open_depth=stack[-1].depth if stack else 0
                )
                section = _open_section(
                    stack=stack,
                    structure=structure,
                    heading_text=paragraph.text,
                    depth=depth,
                    page_number=paragraph.page_number,
                )
                section.content.append(element_id)
                elements.append(
                    HeadingElement(
                        element_id=element_id,
                        page_number=paragraph.page_number,
                        section_path=section.path,
                        bounding_regions=paragraph.bounding_regions,
                        text=paragraph.text,
                    )
                )
            else:
                if stack:
                    stack[-1].section.content.append(element_id)
                elements.append(
                    ParagraphElement(
                        element_id=element_id,
                        page_number=paragraph.page_number,
                        section_path=section_path,
                        bounding_regions=paragraph.bounding_regions,
                        text=paragraph.text,
                    )
                )
        elif item.table is not None:
            table = item.table
            element_id = f"table-{next_element_id}"
            next_element_id += 1

            if stack:
                stack[-1].section.content.append(element_id)
            elements.append(
                TableElement(
                    element_id=element_id,
                    page_number=table.page_number,
                    section_path=section_path,
                    bounding_regions=table.bounding_regions,
                    row_count=table.row_count,
                    column_count=table.column_count,
                    cells=[
                        TableCell(
                            row_index=cell.row_index,
                            column_index=cell.column_index,
                            text=cell.text,
                            row_span=cell.row_span,
                            column_span=cell.column_span,
                        )
                        for cell in table.cells
                    ],
                )
            )

    return DocumentStructure(structure=structure, elements=elements)
