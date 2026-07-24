"""Azure Document Intelligence adapter.

This is the only module (besides `client.py`, which only calls the SDK and
never inspects its response shape) permitted to import
`azure.ai.documentintelligence` types. It translates an Azure `AnalyzeResult`
into the vendor-neutral `RawDocument` model from `models.py`. Every stage
past this module operates exclusively on internal models — see ADR-0004 in
`docs/decisions.md`.
"""

from azure.ai.documentintelligence.models import (
    AnalyzeResult,
    DocumentParagraph,
    DocumentTable,
)
from azure.ai.documentintelligence.models import (
    BoundingRegion as AzureBoundingRegion,
)

from legal_rag.ingestion.exceptions import ExtractionError
from legal_rag.ingestion.models import (
    BoundingRegion,
    RawDocument,
    RawPage,
    RawParagraph,
    RawParagraphRole,
    RawTable,
    RawTableCell,
)

_ROLE_MAP: dict[str, RawParagraphRole] = {
    "title": RawParagraphRole.TITLE,
    "sectionHeading": RawParagraphRole.SECTION_HEADING,
    "pageHeader": RawParagraphRole.PAGE_HEADER,
    "pageFooter": RawParagraphRole.PAGE_FOOTER,
    "footnote": RawParagraphRole.FOOTNOTE,
}


def _enum_value(value: object | None) -> str | None:
    """Return the plain string value of an Azure SDK enum-or-string field.

    Azure SDK enums (e.g. `LengthUnit`, `ParagraphRole`) are `str` subclasses
    whose `str()` yields `"LengthUnit.INCH"`, not `"inch"` — the actual value
    lives on `.value`. Plain strings (which the SDK also accepts/returns in
    some paths) have no `.value` and are returned unchanged.
    """
    if value is None:
        return None
    return getattr(value, "value", value)


def _convert_bounding_regions(
    regions: list[AzureBoundingRegion] | None,
) -> list[BoundingRegion]:
    return [
        BoundingRegion(page_number=region.page_number, polygon=list(region.polygon or []))
        for region in (regions or [])
    ]


def _first_page_number(regions: list[AzureBoundingRegion] | None, *, element_kind: str) -> int:
    if not regions:
        raise ExtractionError(
            f"{element_kind} has no bounding regions; cannot determine page number",
            context={"element_kind": element_kind},
        )
    return regions[0].page_number


def _convert_paragraph(paragraph: DocumentParagraph) -> RawParagraph:
    role_value = _enum_value(paragraph.role) or ""
    return RawParagraph(
        text=paragraph.content,
        role=_ROLE_MAP.get(role_value, RawParagraphRole.TEXT),
        page_number=_first_page_number(paragraph.bounding_regions, element_kind="paragraph"),
        bounding_regions=_convert_bounding_regions(paragraph.bounding_regions),
        source_start=_span_start(paragraph),
        source_end=_span_end(paragraph),
    )


def _convert_table(table: DocumentTable) -> RawTable:
    return RawTable(
        page_number=_first_page_number(table.bounding_regions, element_kind="table"),
        row_count=table.row_count,
        column_count=table.column_count,
        cells=[
            RawTableCell(
                row_index=cell.row_index,
                column_index=cell.column_index,
                text=cell.content,
                row_span=cell.row_span or 1,
                column_span=cell.column_span or 1,
            )
            for cell in table.cells
        ],
        bounding_regions=_convert_bounding_regions(table.bounding_regions),
        source_start=_span_start(table),
        source_end=_span_end(table),
    )


def _span_start(item: object) -> int | None:
    spans = getattr(item, "spans", None) or []
    return getattr(spans[0], "offset", None) if spans else None


def _span_end(item: object) -> int | None:
    spans = getattr(item, "spans", None) or []
    if not spans:
        return None
    start = getattr(spans[0], "offset", None)
    length = getattr(spans[0], "length", None)
    return start + length if start is not None and length is not None else None


def to_raw_document(result: AnalyzeResult) -> RawDocument:
    """Translate an Azure `AnalyzeResult` into a vendor-neutral `RawDocument`."""
    return RawDocument(
        model_id=result.model_id,
        api_version=result.api_version,
        pages=[
            RawPage(
                page_number=page.page_number,
                width=page.width or 0.0,
                height=page.height or 0.0,
                unit=_enum_value(page.unit) or "unknown",
            )
            for page in result.pages
        ],
        paragraphs=[_convert_paragraph(paragraph) for paragraph in (result.paragraphs or [])],
        tables=[_convert_table(table) for table in (result.tables or [])],
    )
