import pytest

from legal_rag.ingestion.discovery import DocumentFormat, SourceDocument, discover
from tests.ingestion.conftest import FakeStorageBackend


@pytest.mark.parametrize(
    ("ref", "expected_format"),
    [
        ("merger-agreement.pdf", DocumentFormat.PDF),
        ("MERGER-AGREEMENT.PDF", DocumentFormat.PDF),
        ("exhibit.jpg", DocumentFormat.JPEG),
        ("exhibit.jpeg", DocumentFormat.JPEG),
        ("scan.png", DocumentFormat.PNG),
        ("scan.bmp", DocumentFormat.BMP),
        ("scan.tif", DocumentFormat.TIFF),
        ("scan.tiff", DocumentFormat.TIFF),
        ("scan.heif", DocumentFormat.HEIF),
        ("filing.htm", DocumentFormat.UNKNOWN),
        ("filing.txt", DocumentFormat.UNKNOWN),
        ("no-extension", DocumentFormat.UNKNOWN),
    ],
)
def test_discover_classifies_format_by_extension(ref: str, expected_format: DocumentFormat) -> None:
    storage = FakeStorageBackend({ref: b"content"})

    documents = list(discover(storage))

    assert documents == [SourceDocument(ref=ref, format=expected_format)]


def test_discover_yields_every_ref_including_unknown_format() -> None:
    storage = FakeStorageBackend({"good.pdf": b"1", "unsupported.txt": b"2", "another.pdf": b"3"})

    documents = list(discover(storage))

    assert len(documents) == 3
    assert [doc.format for doc in documents] == [
        DocumentFormat.PDF,
        DocumentFormat.UNKNOWN,
        DocumentFormat.PDF,
    ]


def test_discover_empty_storage_yields_nothing() -> None:
    storage = FakeStorageBackend({})

    assert list(discover(storage)) == []
