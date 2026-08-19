"""Source document enumeration and format classification.

Discovery is a pure classification step: it enumerates refs from a
`StorageBackend` and tags each with a detected `DocumentFormat` by file
extension. It does not open files, and it does not filter anything out —
every ref is yielded, including ones with an unsupported or unknown format,
so every source document gets a manifest entry (ADR-0006) even if it's
later rejected. Actually validating that a file is readable belongs to
`normalization.py`, which has to open the file anyway.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from legal_rag.ingestion.storage.base import StorageBackend


class DocumentFormat(StrEnum):
    PDF = "pdf"
    JPEG = "jpeg"
    PNG = "png"
    BMP = "bmp"
    TIFF = "tiff"
    HEIF = "heif"
    UNKNOWN = "unknown"


_EXTENSION_MAP: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".jpg": DocumentFormat.JPEG,
    ".jpeg": DocumentFormat.JPEG,
    ".png": DocumentFormat.PNG,
    ".bmp": DocumentFormat.BMP,
    ".tif": DocumentFormat.TIFF,
    ".tiff": DocumentFormat.TIFF,
    ".heif": DocumentFormat.HEIF,
}

SUPPORTED_FORMATS = frozenset(_EXTENSION_MAP.values())


@dataclass(frozen=True)
class SourceDocument:
    ref: str
    format: DocumentFormat


def _detect_format(ref: str) -> DocumentFormat:
    suffix = PurePosixPath(ref).suffix.lower()
    return _EXTENSION_MAP.get(suffix, DocumentFormat.UNKNOWN)


def discover(storage: StorageBackend) -> Iterator[SourceDocument]:
    """Yield a `SourceDocument` for every ref the storage backend reports."""
    for ref in storage.list_source_documents():
        yield SourceDocument(ref=ref, format=_detect_format(ref))
