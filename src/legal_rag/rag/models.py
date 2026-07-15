"""Domain models for the RAG layer.

`Chunk` is the unit of retrieval — a new, separately-versioned schema that
*references* the ingestion layer's `DocumentRecord` (by `document_id` and
`element_ids`) rather than extending it, keeping the ingestion schema frozen.
`ScoredChunk`, `Citation`, and `Answer` are the retrieval/answering value
objects the UI consumes.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A retrieval unit derived from one document section.

    `text` is the verbatim source text (what gets shown and cited);
    `embed_text` is what gets embedded — the document title and section
    path are prepended so generic clause language embeds with its identity.
    """

    chunk_schema_version: Literal["1.0"] = "1.0"
    chunk_id: str
    document_id: str
    document_title: str
    section_path: list[str] = Field(default_factory=list)
    page_start: int
    page_end: int
    source_anchor: str | None = None
    element_ids: list[str]
    chunk_type: Literal["text", "table"]
    text: str
    embed_text: str


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float


class Citation(BaseModel):
    """A resolved, human-readable citation for one chunk used in an answer."""

    marker: int
    document_title: str
    section_path: list[str]
    page_start: int
    page_end: int
    chunk_id: str
    snippet: str
    source_url: str | None = None
    source_checksum: str | None = None
    source_kind: Literal["court_pdf", "sec_html"] = "court_pdf"
    source_anchor: str | None = None
    accession_number: str | None = None

    @property
    def display(self) -> str:
        section = " › ".join(self.section_path) if self.section_path else "(document body)"
        pages = (
            f"p. {self.page_start}"
            if self.page_start == self.page_end
            else f"pp. {self.page_start}–{self.page_end}"
        )
        location = pages if self.source_kind == "court_pdf" else section
        return f"{self.document_title} — {section} ({location})"


class Answer(BaseModel):
    question: str
    text: str
    citations: list[Citation]
    grounded: bool
