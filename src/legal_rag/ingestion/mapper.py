"""Assembles the final `DocumentRecord` from a built structure and metadata.

`structure.py` already produces the final `Section`/`Element` types, so this
module's job is plain field assembly: combine those with the raw document's
page/model metadata and the source file's identity into one `DocumentRecord`.
It is a pure function of its inputs — no I/O, no clock reads — so callers
(`pipeline.py`) control the timestamp and pass it in, keeping this testable
with fixed expected output.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from legal_rag.ingestion.models import (
    DocumentRecord,
    ExtractionInfo,
    ExtractionStatus,
    PageInfo,
    RawDocument,
    SecMetadata,
    SourceInfo,
)
from legal_rag.ingestion.structure import DocumentStructure


def compute_document_id(content: bytes) -> str:
    """Return the stable, content-addressed document ID for `content`."""
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class SourceFileInfo:
    file_name: str
    file_path: str
    content: bytes
    sec_metadata: SecMetadata | None = None


def to_document_record(
    *,
    document_structure: DocumentStructure,
    raw_document: RawDocument,
    source: SourceFileInfo,
    pipeline_version: str,
    extracted_at: datetime,
    extraction_status: ExtractionStatus,
    warnings: list[str] | None = None,
) -> DocumentRecord:
    document_id = compute_document_id(source.content)

    return DocumentRecord(
        document_id=document_id,
        source=SourceInfo(
            file_name=source.file_name,
            file_path=source.file_path,
            file_hash_sha256=document_id,
            sec_metadata=source.sec_metadata,
        ),
        extraction=ExtractionInfo(
            model_id=raw_document.model_id,
            api_version=raw_document.api_version,
            pipeline_version=pipeline_version,
            extracted_at=extracted_at,
            status=extraction_status,
            warnings=warnings or [],
        ),
        page_count=len(raw_document.pages),
        pages=[
            PageInfo(
                page_number=page.page_number,
                width=page.width,
                height=page.height,
                unit=page.unit,
            )
            for page in raw_document.pages
        ],
        structure=document_structure.structure,
        elements=document_structure.elements,
    )
