import pytest

from legal_rag.ingestion.discovery import DocumentFormat, SourceDocument
from legal_rag.ingestion.exceptions import CorruptedDocumentError, UnsupportedFormatError
from legal_rag.ingestion.normalization import NormalizedDocument, normalize
from tests.ingestion.conftest import FakeStorageBackend

_VALID_CONTENT: dict[DocumentFormat, bytes] = {
    DocumentFormat.PDF: b"%PDF-1.7\n...",
    DocumentFormat.JPEG: b"\xff\xd8\xff\xe0...",
    DocumentFormat.PNG: b"\x89PNG\r\n\x1a\n...",
    DocumentFormat.BMP: b"BM...",
    DocumentFormat.TIFF: b"II*\x00...",
    DocumentFormat.HEIF: b"\x00\x00\x00\x18ftypheic...",
}


@pytest.mark.parametrize(
    ("document_format", "expected_content_type"),
    [
        (DocumentFormat.PDF, "application/pdf"),
        (DocumentFormat.JPEG, "image/jpeg"),
        (DocumentFormat.PNG, "image/png"),
        (DocumentFormat.BMP, "image/bmp"),
        (DocumentFormat.TIFF, "image/tiff"),
        (DocumentFormat.HEIF, "image/heif"),
    ],
)
def test_normalize_accepts_valid_signature_for_each_supported_format(
    document_format: DocumentFormat, expected_content_type: str
) -> None:
    content = _VALID_CONTENT[document_format]
    storage = FakeStorageBackend({"doc": content})
    source = SourceDocument(ref="doc", format=document_format)

    result = normalize(source, storage)

    assert result == NormalizedDocument(
        ref="doc", content=content, content_type=expected_content_type
    )


def test_normalize_rejects_unsupported_format_without_reading_storage() -> None:
    storage = FakeStorageBackend({})  # "doc" intentionally absent
    source = SourceDocument(ref="doc", format=DocumentFormat.UNKNOWN)

    with pytest.raises(UnsupportedFormatError):
        normalize(source, storage)


def test_normalize_rejects_empty_content() -> None:
    storage = FakeStorageBackend({"doc": b""})
    source = SourceDocument(ref="doc", format=DocumentFormat.PDF)

    with pytest.raises(CorruptedDocumentError):
        normalize(source, storage)


def test_normalize_rejects_content_that_does_not_match_claimed_format() -> None:
    storage = FakeStorageBackend({"doc": b"not actually a pdf"})
    source = SourceDocument(ref="doc", format=DocumentFormat.PDF)

    with pytest.raises(CorruptedDocumentError):
        normalize(source, storage)


def test_normalize_rejects_heif_without_ftyp_box() -> None:
    storage = FakeStorageBackend({"doc": b"\x00\x00\x00\x18not-a-heif-file........"})
    source = SourceDocument(ref="doc", format=DocumentFormat.HEIF)

    with pytest.raises(CorruptedDocumentError):
        normalize(source, storage)
