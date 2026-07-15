"""Structure-aware chunking of `DocumentRecord`s into retrieval units.

Strategy (per the architecture review, §9):
- Children are contiguous paragraph runs *within one section* (grouped by
  `section_path`), capped at `max_chars` and split only at paragraph
  boundaries — never mid-sentence, never on page boundaries.
- Tables are atomic chunks, serialized row-by-row with a header line.
- Heading elements contribute to `section_path` (already resolved by the
  ingestion parser), not to chunk text.
- Bare footnote-marker fragments (short, digits-only paragraphs observed in
  live extractions, e.g. "14") are dropped — they carry no retrievable
  content and would pollute BM25 statistics.
- Every chunk's `embed_text` is prefixed with the document title and section
  path, so generic clause language ("the Court finds...") embeds together
  with its identity.
"""

from legal_rag.ingestion.models import DocumentRecord, TableElement
from legal_rag.rag.models import Chunk


def _is_footnote_marker(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) <= 4 and stripped.replace(".", "").isdigit()


def _serialize_table(table: TableElement) -> str:
    rows: dict[int, dict[int, str]] = {}
    for cell in table.cells:
        rows.setdefault(cell.row_index, {})[cell.column_index] = cell.text.strip()
    lines = []
    for row_index in sorted(rows):
        cells = rows[row_index]
        lines.append(" | ".join(cells.get(i, "") for i in sorted(cells)))
    return "\n".join(lines)


def _embed_text(title: str, section_path: list[str], text: str) -> str:
    prefix = " › ".join([title, *section_path])
    return f"{prefix}\n\n{text}"


class _ChunkBuilder:
    def __init__(self, document_id: str, title: str, max_chars: int) -> None:
        self._document_id = document_id
        self._title = title
        self._max_chars = max_chars
        self._chunks: list[Chunk] = []
        self._section_path: list[str] = []
        self._texts: list[str] = []
        self._element_ids: list[str] = []
        self._pages: list[int] = []
        self._source_anchors: list[str] = []
        self._source_spans: list[tuple[int, int]] = []

    def _flush(self) -> None:
        if not self._texts:
            return
        text = "\n\n".join(self._texts)
        self._chunks.append(
            Chunk(
                chunk_id=f"{self._document_id[:12]}-{len(self._chunks):04d}",
                document_id=self._document_id,
                document_title=self._title,
                section_path=list(self._section_path),
                page_start=min(self._pages),
                page_end=max(self._pages),
                source_anchor=next(iter(self._source_anchors), None),
                source_start=min((start for start, _ in self._source_spans), default=None),
                source_end=max((end for _, end in self._source_spans), default=None),
                element_ids=list(self._element_ids),
                chunk_type="text",
                text=text,
                embed_text=_embed_text(self._title, self._section_path, text),
            )
        )
        self._texts, self._element_ids, self._pages, self._source_anchors, self._source_spans = (
            [],
            [],
            [],
            [],
            [],
        )

    def add_paragraph(
        self,
        *,
        text: str,
        element_id: str,
        page: int,
        path: list[str],
        source_anchor: str | None,
        source_start: int | None,
        source_end: int | None,
    ) -> None:
        if _is_footnote_marker(text):
            return
        if path != self._section_path:
            self._flush()
            self._section_path = path
        prospective = sum(len(t) for t in self._texts) + len(text)
        if self._texts and prospective > self._max_chars:
            self._flush()
        self._texts.append(text)
        self._element_ids.append(element_id)
        self._pages.append(page)
        if source_anchor:
            self._source_anchors.append(source_anchor)
        if source_start is not None and source_end is not None:
            self._source_spans.append((source_start, source_end))

    def add_table(self, table: TableElement) -> None:
        self._flush()
        self._section_path = table.section_path
        text = _serialize_table(table)
        if not text.strip():
            return
        self._chunks.append(
            Chunk(
                chunk_id=f"{self._document_id[:12]}-{len(self._chunks):04d}",
                document_id=self._document_id,
                document_title=self._title,
                section_path=list(table.section_path),
                page_start=table.page_number,
                page_end=table.page_number,
                source_anchor=table.source_anchor,
                source_start=table.source_start,
                source_end=table.source_end,
                element_ids=[table.element_id],
                chunk_type="table",
                text=text,
                embed_text=_embed_text(self._title, table.section_path, text),
            )
        )

    def finish(self) -> list[Chunk]:
        self._flush()
        return self._chunks


def chunk_document(record: DocumentRecord, *, title: str, max_chars: int = 1800) -> list[Chunk]:
    """Chunk one processed document into typed retrieval units."""
    builder = _ChunkBuilder(record.document_id, title, max_chars)
    for element in record.elements:
        if element.type == "paragraph":
            builder.add_paragraph(
                text=element.text,
                element_id=element.element_id,
                page=element.page_number,
                path=element.section_path,
                source_anchor=element.source_anchor,
                source_start=element.source_start,
                source_end=element.source_end,
            )
        elif element.type == "table":
            builder.add_table(element)
        # headings contribute via section_path, not chunk text
    return builder.finish()
