"""Semantic (business-rule) validation of an assembled `DocumentRecord`.

This is the second validation layer described in the approved error-handling
design: Pydantic already enforces schema *shape* when `DocumentRecord` is
constructed (`SchemaValidationError`, raised by the caller if construction
fails). This module checks things Pydantic cannot express — a document can
be perfectly shape-valid and still be semantically empty or internally
inconsistent (e.g. a section referencing an element that doesn't exist,
which would indicate a bug in `structure.py` rather than bad source data).

`validate()` is a pure function returning a `ValidationResult`, not an
exception — `pipeline.py` decides whether a failed result becomes a raised
`SemanticValidationError` and how it's recorded.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from legal_rag.ingestion.models import DocumentRecord, HeadingElement, ParagraphElement, Section


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def _check_has_pages(record: DocumentRecord) -> list[str]:
    if record.page_count <= 0:
        return ["page_count must be greater than 0"]
    return []


def _check_page_count_matches_pages(record: DocumentRecord) -> list[str]:
    if len(record.pages) != record.page_count:
        return [f"page_count ({record.page_count}) does not match len(pages) ({len(record.pages)})"]
    return []


def _check_has_elements(record: DocumentRecord) -> list[str]:
    if not record.elements:
        return ["document has no extracted elements"]
    return []


def _check_element_ids_are_unique(record: DocumentRecord) -> list[str]:
    ids = [element.element_id for element in record.elements]
    duplicates = sorted({element_id for element_id in ids if ids.count(element_id) > 1})
    if duplicates:
        return [f"duplicate element_id(s): {duplicates}"]
    return []


def _check_element_page_numbers_in_range(record: DocumentRecord) -> list[str]:
    return [
        f"element {element.element_id} references out-of-range page_number {element.page_number}"
        for element in record.elements
        if not (1 <= element.page_number <= record.page_count)
    ]


def _check_non_empty_text(record: DocumentRecord) -> list[str]:
    return [
        f"element {element.element_id} has empty text"
        for element in record.elements
        if isinstance(element, ParagraphElement | HeadingElement) and not element.text.strip()
    ]


def _check_section_content_references_exist(record: DocumentRecord) -> list[str]:
    element_ids = {element.element_id for element in record.elements}
    errors: list[str] = []

    def walk(sections: list[Section]) -> None:
        for section in sections:
            errors.extend(
                f"section {section.section_id} references unknown element_id {element_id}"
                for element_id in section.content
                if element_id not in element_ids
            )
            walk(section.children)

    walk(record.structure)
    return errors


def _check_source_spans(record: DocumentRecord) -> list[str]:
    errors: list[str] = []
    for element in record.elements:
        if (element.source_start is None) != (element.source_end is None):
            errors.append(f"element {element.element_id} has an incomplete source span")
        if (
            element.source_start is not None
            and element.source_end is not None
            and element.source_end <= element.source_start
        ):
            errors.append(f"element {element.element_id} has an invalid source span")
    return errors


def _check_sections_are_well_formed(record: DocumentRecord) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    def walk(sections: list[Section], parent: Section | None = None) -> None:
        for section in sections:
            if section.section_id in seen_ids:
                errors.append(f"duplicate section_id {section.section_id}")
            seen_ids.add(section.section_id)
            expected_path = [*parent.path, section.heading] if parent else [section.heading]
            if section.path != expected_path:
                errors.append(f"section {section.section_id} has a malformed heading path")
            if parent and section.level <= parent.level:
                errors.append(f"section {section.section_id} is not nested below its parent")
            if not section.content:
                errors.append(f"section {section.section_id} is orphaned from extracted content")
            walk(section.children, section)

    walk(record.structure)
    return errors


def _check_sec_locators(record: DocumentRecord) -> list[str]:
    if record.source.sec_metadata is None:
        return []
    errors: list[str] = []
    if not record.source.sec_metadata.canonical_url:
        errors.append("SEC document is missing its canonical source URL")
    headings = [element for element in record.elements if isinstance(element, HeadingElement)]
    anchors = [heading.source_anchor for heading in headings if heading.source_anchor]
    if len(anchors) != len(set(anchors)):
        errors.append("SEC document contains duplicate heading anchors")
    for element in record.elements:
        if element.source_start is None or element.source_end is None:
            errors.append(f"SEC element {element.element_id} has no exact source span")
    return errors


_CHECKS: list[Callable[[DocumentRecord], list[str]]] = [
    _check_has_pages,
    _check_page_count_matches_pages,
    _check_has_elements,
    _check_element_ids_are_unique,
    _check_element_page_numbers_in_range,
    _check_non_empty_text,
    _check_section_content_references_exist,
    _check_source_spans,
    _check_sections_are_well_formed,
    _check_sec_locators,
]


def validate(record: DocumentRecord) -> ValidationResult:
    errors = [error for check in _CHECKS for error in check(record)]
    return ValidationResult(is_valid=not errors, errors=errors)
