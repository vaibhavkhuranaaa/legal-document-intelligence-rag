"""Native, rate-limited ingestion support for a curated SEC EDGAR HTML release.

The SEC sources remain the canonical record. This module only downloads named
release inputs, records their immutable identity, and turns semantic HTML into
the existing vendor-neutral ``RawDocument`` boundary. It deliberately does not
crawl EDGAR or infer page numbers from HTML.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from legal_rag.ingestion.mapper import SourceFileInfo, to_document_record
from legal_rag.ingestion.models import (
    ExtractionStatus,
    RawDocument,
    RawPage,
    RawParagraph,
    RawParagraphRole,
    RawTable,
    RawTableCell,
    SecMetadata,
)
from legal_rag.ingestion.structure import build_structure

_HEADING_PREFIXES = ("article ", "section ", "schedule ", "exhibit ")
_BLOCK_TAGS = frozenset({"p", "li", "h1", "h2", "h3", "h4", "h5", "h6"})


@dataclass(frozen=True)
class SecFilingInput:
    """The minimum provenance required for one explicitly approved EDGAR input."""

    canonical_url: str
    cik: str
    accession_number: str
    form_type: str
    filing_date: str
    company_name: str
    exhibit_identity: str


@dataclass
class _Capture:
    tag: str
    anchor: str | None
    parts: list[str] = field(default_factory=list)
    source_start: int | None = None
    source_end: int | None = None


class _EdgarHtmlParser(HTMLParser):
    """Small, tolerant DOM-to-RawDocument parser for release-controlled filings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[RawParagraph] = []
        self.tables: list[RawTable] = []
        self._anchors: list[str | None] = []
        self._captures: list[_Capture] = []
        self._table_anchor: str | None = None
        self._table_rows: list[list[str]] = []
        self._table_start: int | None = None
        self._table_end: int | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None
        self._text_offset = 0

    @staticmethod
    def _anchor(attrs: list[tuple[str, str | None]]) -> str | None:
        return next((value for key, value in attrs if key.lower() == "id" and value), None)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        inherited_anchor = next((item for item in reversed(self._anchors) if item), None)
        anchor = self._anchor(attrs) or inherited_anchor
        self._anchors.append(self._anchor(attrs))
        if tag in _BLOCK_TAGS:
            self._captures.append(_Capture(tag=tag, anchor=anchor))
        elif tag == "table":
            self._table_anchor = anchor
            self._table_rows = []
            self._table_start = None
            self._table_end = None
        elif tag == "tr" and self._table_anchor is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        for capture in self._captures:
            if capture.source_start is None:
                capture.source_start = self._text_offset
            capture.parts.append(data)
            capture.source_end = self._text_offset + len(data)
        if self._cell_parts is not None:
            self._cell_parts.append(data)
        if self._table_anchor is not None:
            if self._table_start is None:
                self._table_start = self._text_offset
            self._table_end = self._text_offset + len(data)
        self._text_offset += len(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _BLOCK_TAGS:
            for index in range(len(self._captures) - 1, -1, -1):
                capture = self._captures[index]
                if capture.tag == tag:
                    self._captures.pop(index)
                    self._emit_paragraph(capture)
                    break
        elif tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
            value = " ".join("".join(self._cell_parts).split())
            self._row.append(value)
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self._table_rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table_anchor is not None:
            self._emit_table()
            self._table_anchor = None
        if self._anchors:
            self._anchors.pop()

    def close(self) -> None:
        super().close()
        # Tolerate malformed release HTML by retaining captures that never closed.
        for capture in self._captures:
            self._emit_paragraph(capture)
        self._captures.clear()

    def _emit_paragraph(self, capture: _Capture) -> None:
        text = " ".join("".join(capture.parts).split())
        if not text:
            return
        role = (
            RawParagraphRole.SECTION_HEADING
            if capture.tag.startswith("h") or text.lower().startswith(_HEADING_PREFIXES)
            else RawParagraphRole.TEXT
        )
        self.paragraphs.append(
            RawParagraph(
                text=text,
                role=role,
                page_number=1,
                source_anchor=capture.anchor,
                source_start=capture.source_start,
                source_end=capture.source_end,
            )
        )

    def _emit_table(self) -> None:
        if not self._table_rows:
            return
        width = max(len(row) for row in self._table_rows)
        cells = [
            RawTableCell(row_index=row_index, column_index=column_index, text=value)
            for row_index, row in enumerate(self._table_rows)
            for column_index, value in enumerate(row)
        ]
        self.tables.append(
            RawTable(
                page_number=1,
                row_count=len(self._table_rows),
                column_count=width,
                cells=cells,
                source_anchor=self._table_anchor,
                source_start=self._table_start,
                source_end=self._table_end,
            )
        )


def parse_edgar_html(content: bytes) -> RawDocument:
    """Parse one native filing without representing its HTML as paginated text."""
    parser = _EdgarHtmlParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    return RawDocument(
        model_id="sec-edgar-native-html",
        api_version="html-v1",
        pages=[RawPage(page_number=1, width=0, height=0, unit="html-document")],
        paragraphs=parser.paragraphs,
        tables=parser.tables,
    )


def to_sec_document_record(*, filing: SecFilingInput, content: bytes, pipeline_version: str):
    """Build the stable record consumed by validation, chunking, and indexing."""
    raw_document = parse_edgar_html(content)
    structure = build_structure(raw_document)
    return to_document_record(
        document_structure=structure,
        raw_document=raw_document,
        source=SourceFileInfo(
            file_name=filing.accession_number.replace("-", "") + ".html",
            file_path=filing.canonical_url,
            content=content,
            sec_metadata=SecMetadata(
                cik=filing.cik,
                accession_number=filing.accession_number,
                form_type=filing.form_type,
                filing_date=datetime.fromisoformat(filing.filing_date).date(),
                company_name=filing.company_name,
                exhibit_identity=filing.exhibit_identity,
                canonical_url=filing.canonical_url,
            ),
        ),
        pipeline_version=pipeline_version,
        extracted_at=datetime.now(UTC),
        extraction_status=ExtractionStatus.SUCCESS,
        warnings=structure.warnings,
    )


class SecEdgarClient:
    """A small, polite fetcher for approved URLs only (never a crawler)."""

    def __init__(self, *, user_agent: str, min_interval_seconds: float = 0.11) -> None:
        if "<" not in user_agent or ">" not in user_agent:
            raise ValueError("SEC User-Agent must identify an organization and contact email")
        self._user_agent = user_agent
        self._min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0

    def fetch(self, canonical_url: str, *, timeout_seconds: float = 30.0) -> bytes:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - elapsed)
        request = Request(canonical_url, headers={"User-Agent": self._user_agent})  # noqa: S310
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            content = response.read()
        self._last_request_at = time.monotonic()
        return content
