"""Domain models for the ingestion pipeline.

Two layers of models live here:

- Raw* models: a vendor-neutral representation of what Azure Document
  Intelligence extracted, produced by the adapter layer. No stage past the
  adapter may depend on Azure SDK types — only on these.
- DocumentRecord (and its nested models): the stable, versioned output
  schema written to storage and consumed by every future phase.

ManifestEntry / RunReport capture per-run, per-document processing outcomes
and are independent of both of the above.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ExtractionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class BoundingRegion(BaseModel):
    page_number: int
    polygon: list[float] = Field(default_factory=list)


class RawParagraphRole(StrEnum):
    TITLE = "title"
    SECTION_HEADING = "sectionHeading"
    PAGE_HEADER = "pageHeader"
    PAGE_FOOTER = "pageFooter"
    FOOTNOTE = "footnote"
    TEXT = "text"


class RawParagraph(BaseModel):
    text: str
    role: RawParagraphRole
    page_number: int
    bounding_regions: list[BoundingRegion] = Field(default_factory=list)


class RawTableCell(BaseModel):
    row_index: int
    column_index: int
    text: str
    row_span: int = 1
    column_span: int = 1


class RawTable(BaseModel):
    page_number: int
    row_count: int
    column_count: int
    cells: list[RawTableCell]
    bounding_regions: list[BoundingRegion] = Field(default_factory=list)


class RawPage(BaseModel):
    page_number: int
    width: float
    height: float
    unit: str


class RawDocument(BaseModel):
    """Vendor-neutral extraction result produced by the adapter layer."""

    model_id: str
    api_version: str
    pages: list[RawPage]
    paragraphs: list[RawParagraph]
    tables: list[RawTable]


class SecMetadata(BaseModel):
    cik: str | None = None
    accession_number: str | None = None
    form_type: str | None = None
    filing_date: date | None = None
    company_name: str | None = None


class SourceInfo(BaseModel):
    file_name: str
    file_path: str
    file_hash_sha256: str
    sec_metadata: SecMetadata | None = None


class ExtractionInfo(BaseModel):
    model_id: str
    api_version: str
    pipeline_version: str
    extracted_at: datetime
    status: ExtractionStatus
    warnings: list[str] = Field(default_factory=list)


class PageInfo(BaseModel):
    page_number: int
    width: float
    height: float
    unit: str


class TableCell(BaseModel):
    row_index: int
    column_index: int
    text: str
    row_span: int = 1
    column_span: int = 1


class ElementBase(BaseModel):
    element_id: str
    page_number: int
    section_path: list[str] = Field(default_factory=list)
    bounding_regions: list[BoundingRegion] = Field(default_factory=list)


class ParagraphElement(ElementBase):
    type: Literal["paragraph"] = "paragraph"
    text: str


class HeadingElement(ElementBase):
    type: Literal["heading"] = "heading"
    text: str


class TableElement(ElementBase):
    type: Literal["table"] = "table"
    row_count: int
    column_count: int
    cells: list[TableCell]


Element = Annotated[ParagraphElement | HeadingElement | TableElement, Field(discriminator="type")]


class Section(BaseModel):
    section_id: str
    heading: str
    level: int
    page_number: int
    path: list[str]
    children: list[Section] = Field(default_factory=list)
    content: list[str] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    """The stable, versioned JSON schema consumed by every downstream phase."""

    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    source: SourceInfo
    extraction: ExtractionInfo
    page_count: int
    pages: list[PageInfo]
    structure: list[Section]
    elements: list[Element]


class ManifestEntry(BaseModel):
    document_id: str | None = None
    run_id: str
    correlation_id: str
    source_file: str
    processing_duration_seconds: float
    page_count: int | None = None
    output_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    extraction_status: ExtractionStatus
    error: str | None = None


class RunReport(BaseModel):
    run_id: str
    pipeline_version: str
    started_at: datetime
    completed_at: datetime | None = None
    entries: list[ManifestEntry] = Field(default_factory=list)
