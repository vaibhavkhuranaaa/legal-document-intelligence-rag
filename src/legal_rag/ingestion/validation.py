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


_CHECKS: list[Callable[[DocumentRecord], list[str]]] = [
    _check_has_pages,
    _check_page_count_matches_pages,
    _check_has_elements,
    _check_element_ids_are_unique,
    _check_element_page_numbers_in_range,
    _check_non_empty_text,
    _check_section_content_references_exist,
]


def validate(record: DocumentRecord) -> ValidationResult:
    errors = [error for check in _CHECKS for error in check(record)]
    return ValidationResult(is_valid=not errors, errors=errors)
