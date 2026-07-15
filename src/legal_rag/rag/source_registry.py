"""Public-source provenance registry for the curated legal corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class CorpusDocument:
    """A public corpus record whose checksum identifies its processed document."""

    document_id: str
    local_filename: str
    display_name: str
    case_name: str
    docket_number: str
    court: str
    jurisdiction: str
    year: int
    legal_topic: str
    source_url: str

    def source_page_url(self, page: int) -> str:
        """Return a browser-supported best-effort PDF page fragment."""
        if page < 1:
            raise ValueError("page must be positive")
        parts = urlsplit(self.source_url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, f"page={page}"))


class SourceRegistry:
    """Validated source-of-truth registry, indexed by checksum/document id."""

    def __init__(self, documents: list[CorpusDocument]) -> None:
        self._documents = documents
        self._by_document_id = {document.document_id: document for document in documents}
        if len(self._by_document_id) != len(documents):
            raise ValueError("dataset manifest contains duplicate document checksums")

    @property
    def documents(self) -> list[CorpusDocument]:
        return list(self._documents)

    @classmethod
    def load(cls, path: Path) -> SourceRegistry:
        payload = json.loads(path.read_text())
        documents = [_parse_document(item) for item in payload.get("documents", [])]
        if not documents:
            raise ValueError("dataset manifest contains no documents")
        return cls(documents)

    def get(self, document_id: str) -> CorpusDocument | None:
        return self._by_document_id.get(document_id.lower())

    def require(self, document_id: str) -> CorpusDocument:
        document = self.get(document_id)
        if document is None:
            raise ValueError(f"no public source is registered for document {document_id}")
        return document

    def validate_document_ids(self, document_ids: list[str]) -> None:
        for document_id in document_ids:
            self.require(document_id)

    def verify_source_urls(self, *, timeout_seconds: float = 15.0) -> None:
        """Fail when a canonical public source no longer responds successfully.

        This is an operator release check, deliberately not a web-request dependency.
        """
        for document in self._documents:
            request = Request(document.source_url, method="HEAD")  # noqa: S310
            try:
                with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                    if response.status >= 400:
                        raise ValueError(f"{document.source_url} returned HTTP {response.status}")
            except Exception as exc:
                raise ValueError(f"public source is unavailable: {document.source_url}") from exc


def _parse_document(item: dict) -> CorpusDocument:
    checksum = str(item.get("sha256", "")).lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        raise ValueError(f"invalid sha256 for {item.get('local_filename', 'unknown document')}")
    source_url = str(item.get("source_url", ""))
    parsed = urlsplit(source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"source_url must be an absolute HTTPS URL: {source_url}")
    required = (
        "local_filename",
        "display_name",
        "case_name",
        "docket_number",
        "court",
        "jurisdiction",
        "legal_topic",
    )
    missing = [key for key in required if not item.get(key)]
    if missing:
        raise ValueError(f"manifest record is missing {', '.join(missing)}")
    return CorpusDocument(
        document_id=checksum,
        local_filename=str(item["local_filename"]),
        display_name=str(item["display_name"]),
        case_name=str(item["case_name"]),
        docket_number=str(item["docket_number"]),
        court=str(item["court"]),
        jurisdiction=str(item["jurisdiction"]),
        year=int(item["year"]),
        legal_topic=str(item["legal_topic"]),
        source_url=source_url,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the public legal-corpus registry")
    parser.add_argument("--manifest", type=Path, default=Path("data/dataset_manifest.json"))
    parser.add_argument("--check-urls", action="store_true")
    args = parser.parse_args(argv)
    registry = SourceRegistry.load(args.manifest)
    if args.check_urls:
        registry.verify_source_urls()
    digest = hashlib.sha256(args.manifest.read_bytes()).hexdigest()[:12]
    print(f"Validated {len(registry.documents)} public sources (manifest {digest}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
