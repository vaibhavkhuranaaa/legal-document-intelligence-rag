"""Source document validation and normalization.

This is the stage that actually opens each file (discovery only classified
it by extension). It rejects documents whose format isn't supported, are
empty, or whose content doesn't match their claimed format's file signature
— the "corrupted/unreadable files validated before any Azure call" step from
the approved error-handling design. What survives is a `NormalizedDocument`:
raw bytes plus the MIME content type `client.py` will send to Azure.

No format conversion happens here (e.g. no HTML-to-PDF conversion) — that
capability doesn't exist in this codebase, so `normalize()` only validates
and passes through formats Azure Document Intelligence natively accepts.
"""

from dataclasses import dataclass

from legal_rag.ingestion.discovery import SUPPORTED_FORMATS, DocumentFormat, SourceDocument
from legal_rag.ingestion.exceptions import CorruptedDocumentError, UnsupportedFormatError
from legal_rag.ingestion.storage.base import StorageBackend

_CONTENT_TYPES: dict[DocumentFormat, str] = {
    DocumentFormat.PDF: "application/pdf",
    DocumentFormat.JPEG: "image/jpeg",
    DocumentFormat.PNG: "image/png",
    DocumentFormat.BMP: "image/bmp",
    DocumentFormat.TIFF: "image/tiff",
    DocumentFormat.HEIF: "image/heif",
}

_MAGIC_BYTES: dict[DocumentFormat, tuple[bytes, ...]] = {
    DocumentFormat.PDF: (b"%PDF-",),
    DocumentFormat.JPEG: (b"\xff\xd8\xff",),
    DocumentFormat.PNG: (b"\x89PNG\r\n\x1a\n",),
    DocumentFormat.BMP: (b"BM",),
    DocumentFormat.TIFF: (b"II*\x00", b"MM\x00*"),
}


@dataclass(frozen=True)
class NormalizedDocument:
    ref: str
    content: bytes
    content_type: str


def _has_valid_signature(document_format: DocumentFormat, content: bytes) -> bool:
    if document_format == DocumentFormat.HEIF:
        # The ftyp box appears a few bytes in, not at offset 0.
        return b"ftyp" in content[:16]
    signatures = _MAGIC_BYTES.get(document_format, ())
    return any(content.startswith(signature) for signature in signatures)


def normalize(document: SourceDocument, storage: StorageBackend) -> NormalizedDocument:
    """Validate and read a `SourceDocument`, returning bytes ready for Azure.

    Raises `UnsupportedFormatError` if the format isn't one Azure Document
    Intelligence's layout model accepts, and `CorruptedDocumentError` if the
    document is empty or its content doesn't match its claimed format.
    """
    if document.format not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"unsupported document format: {document.ref!r}",
            context={"ref": document.ref, "format": document.format.value},
        )

    content = storage.read_source_document(document.ref)

    if not content:
        raise CorruptedDocumentError(
            f"source document is empty: {document.ref!r}",
            context={"ref": document.ref},
        )

    if not _has_valid_signature(document.format, content):
        raise CorruptedDocumentError(
            f"source document content does not match expected format "
            f"{document.format.value}: {document.ref!r}",
            context={"ref": document.ref, "format": document.format.value},
        )

    return NormalizedDocument(
        ref=document.ref,
        content=content,
        content_type=_CONTENT_TYPES[document.format],
    )
