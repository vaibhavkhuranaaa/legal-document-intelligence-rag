"""Reconstructs a section hierarchy from Azure's flat paragraph/table stream.

Azure Document Intelligence's `prebuilt-layout` model does not return a
heading hierarchy — every heading paragraph is tagged either `title` or
`sectionHeading`, with no depth information. This module infers depth from
the heading text's own numbering convention (e.g. "ARTICLE I", "1.1",
"(a)", "I.", "A."), which is how legal documents are actually structured.
This is a heuristic, not a guarantee, as noted in the approved Phase 1
design (Section 3: Azure Document Intelligence limitations).

Heading conventions are represented as a small, extensible registry of
`_HeadingStyle` entries rather than a fixed if/elif chain, so future styles
(e.g. "Section", "Schedule", "Exhibit") can be added by extending
`_HEADING_STYLES` without changing the resolution algorithm. Each style is
either "absolute" (its own text unambiguously encodes depth, e.g. dotted
decimals) or "relative" (depth is only meaningful relative to which styles
are already open — e.g. a bare "I." or "A." is a sibling if a matching style
is already open on the stack, otherwise a new, deeper level). Relative-style
depth resolution is deterministic and never silently guesses: when a
heading's text is genuinely ambiguous between styles (e.g. "C." is valid as
both a Roman numeral and a letter) and those interpretations match open
sections at *different* depths, the shallowest matching depth is chosen and
a structured warning is recorded — see `_resolve_heading_depth`.

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
from collections.abc import Callable
from dataclasses import dataclass, field

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
_ROMAN_UPPER_PATTERN = re.compile(r"^([IVXLCDM]+)\.\s")
_LETTER_UPPER_PATTERN = re.compile(r"^([A-Z])\.\s")
_LETTER_LOWER_PATTERN = re.compile(r"^([a-z])\.\s")
_ROMAN_LOWER_PATTERN = re.compile(r"^([ivxlcdm]+)\.\s")
_ARTICLE_NUMBER_PATTERN = re.compile(r"^ARTICLE\s+([IVXLCDM]+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _HeadingStyle:
    """A recognized heading numbering convention.

    `absolute_depth`, when set, computes depth directly from the style's own
    matched text (e.g. "ARTICLE" is always depth 1; a dotted decimal's depth
    is its dot count). Left as `None` for "relative" styles, whose depth has
    no meaning on its own — it is only resolved relative to which styles are
    already open (see `_resolve_heading_depth`).
    """

    name: str
    pattern: re.Pattern[str]
    absolute_depth: Callable[[re.Match[str]], int] | None = None


_HEADING_STYLES: tuple[_HeadingStyle, ...] = (
    _HeadingStyle("article", _ARTICLE_PATTERN, absolute_depth=lambda m: 1),
    _HeadingStyle("decimal", _DECIMAL_PATTERN, absolute_depth=lambda m: m.group(1).count(".") + 1),
    _HeadingStyle("sub_item_paren", _SUB_ITEM_PATTERN),
    _HeadingStyle("roman_upper", _ROMAN_UPPER_PATTERN),
    _HeadingStyle("letter_upper", _LETTER_UPPER_PATTERN),
    _HeadingStyle("letter_lower", _LETTER_LOWER_PATTERN),
    _HeadingStyle("roman_lower", _ROMAN_LOWER_PATTERN),
)


@dataclass(frozen=True)
class DocumentStructure:
    structure: list[Section]
    elements: list[Element]
    warnings: list[str] = field(default_factory=list)


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
    styles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _DepthResolution:
    depth: int
    styles: frozenset[str]
    warning: str | None = None


def _roman_to_int(value: str) -> int:
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for character in reversed(value.upper()):
        current = values[character]
        total += -current if current < previous else current
        previous = max(previous, current)
    return total


def _sequence_token(text: str) -> tuple[str, tuple[int, ...], int] | None:
    """Return a branch-scoped numeric heading token when it is unambiguous."""
    article = _ARTICLE_NUMBER_PATTERN.match(text)
    if article:
        return ("article", (), _roman_to_int(article.group(1)))
    decimal = _DECIMAL_PATTERN.match(text)
    if decimal:
        values = tuple(int(value) for value in decimal.group(1).split("."))
        return ("decimal", values[:-1], values[-1])
    return None


def _successor_warning(
    text: str,
    *,
    parent_path: list[str],
    next_values: dict[tuple[tuple[str, ...], str, tuple[int, ...]], int],
) -> str | None:
    token = _sequence_token(text)
    if token is None:
        return None
    style, branch, current = token
    key = (tuple(parent_path), style, branch)
    expected = next_values.get(key)
    next_values[key] = current + 1
    if expected is not None and current != expected:
        return (
            f"unexpected heading successor for {text!r}: expected {expected}, found {current} "
            f"within branch {'.'.join(map(str, branch)) or 'root'}"
        )
    return None


def _min_y(regions: list[BoundingRegion]) -> float:
    if not regions or not regions[0].polygon:
        return 0.0
    return min(regions[0].polygon[1::2])


def _match_styles(text: str) -> list[tuple[_HeadingStyle, re.Match[str]]]:
    matches = []
    for style in _HEADING_STYLES:
        match = style.pattern.match(text)
        if match:
            matches.append((style, match))
    return matches


def _resolve_heading_depth(
    text: str, *, page_number: int, stack: list[_OpenSection]
) -> _DepthResolution:
    """Resolve a heading's nesting depth deterministically — never guesses.

    - No style matches: a new level, one deeper than whatever is open.
    - An absolute style matches (article/decimal): depth comes directly
      from that style's own text, unaffected by what's open.
    - Exactly one relative style's candidates match an open section: reuse
      that section's depth (sibling).
    - No relative candidate matches anything open: a new, deeper level.
    - Multiple relative candidates match open sections at *different*
      depths: genuinely ambiguous — the shallowest matching depth is chosen
      (to avoid artificial over-nesting) and a structured warning is
      returned with the competing interpretations for debugging.
    """
    matches = _match_styles(text)
    if not matches:
        depth = stack[-1].depth + 1 if stack else 1
        return _DepthResolution(depth=depth, styles=frozenset())

    for style, match in matches:
        if style.absolute_depth is not None:
            return _DepthResolution(depth=style.absolute_depth(match), styles=frozenset())

    candidate_names = frozenset(style.name for style, _ in matches)
    matched_depths: dict[int, set[str]] = {}
    for open_section in reversed(stack):
        overlap = open_section.styles & candidate_names
        if overlap:
            matched_depths.setdefault(open_section.depth, set()).update(overlap)

    if not matched_depths:
        depth = stack[-1].depth + 1 if stack else 1
        return _DepthResolution(depth=depth, styles=candidate_names)

    if len(matched_depths) == 1:
        (depth,) = matched_depths.keys()
        return _DepthResolution(depth=depth, styles=candidate_names)

    shallowest = min(matched_depths)
    warning = (
        f"ambiguous heading style for {text!r} (page {page_number}): "
        f"candidate styles {sorted(candidate_names)} matched open sections at "
        f"depths {sorted(matched_depths)}; chose shallowest depth {shallowest} "
        "to avoid artificial over-nesting"
    )
    return _DepthResolution(depth=shallowest, styles=candidate_names, warning=warning)


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
    styles: frozenset[str],
    source_anchor: str | None,
    source_start: int | None,
    source_end: int | None,
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
        source_anchor=source_anchor,
        source_start=source_start,
        source_end=source_end,
    )
    if parent:
        parent.children.append(section)
    else:
        structure.append(section)
    stack.append(_OpenSection(section=section, depth=depth, styles=styles))
    return section


def build_structure(document: RawDocument) -> DocumentStructure:
    structure: list[Section] = []
    elements: list[Element] = []
    warnings: list[str] = []
    stack: list[_OpenSection] = []
    next_element_id = 1
    next_heading_values: dict[tuple[tuple[str, ...], str, tuple[int, ...]], int] = {}

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
                resolution = _resolve_heading_depth(
                    paragraph.text, page_number=paragraph.page_number, stack=stack
                )
                if resolution.warning:
                    warnings.append(resolution.warning)
                parent_path = []
                for open_section in reversed(stack):
                    if open_section.depth < resolution.depth:
                        parent_path = open_section.section.path
                        break
                successor_warning = _successor_warning(
                    paragraph.text,
                    parent_path=parent_path,
                    next_values=next_heading_values,
                )
                if successor_warning:
                    warnings.append(successor_warning)
                section = _open_section(
                    stack=stack,
                    structure=structure,
                    heading_text=paragraph.text,
                    depth=resolution.depth,
                    page_number=paragraph.page_number,
                    styles=resolution.styles,
                    source_anchor=paragraph.source_anchor,
                    source_start=paragraph.source_start,
                    source_end=paragraph.source_end,
                )
                section.content.append(element_id)
                elements.append(
                    HeadingElement(
                        element_id=element_id,
                        page_number=paragraph.page_number,
                        section_path=section.path,
                        bounding_regions=paragraph.bounding_regions,
                        source_anchor=paragraph.source_anchor,
                        source_start=paragraph.source_start,
                        source_end=paragraph.source_end,
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
                        source_anchor=stack[-1].section.source_anchor if stack else None,
                        source_start=paragraph.source_start,
                        source_end=paragraph.source_end,
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
                source_anchor=table.source_anchor,
                source_start=table.source_start,
                source_end=table.source_end,
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

    return DocumentStructure(structure=structure, elements=elements, warnings=warnings)
