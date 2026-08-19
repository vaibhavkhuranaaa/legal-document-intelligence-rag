"""Loads processed documents and resolves their human titles.

The dataset manifest (`data/dataset_manifest.json`) is the curated corpus
registry; processed `DocumentRecord`s are matched to it by local filename so
chunks and citations carry real case names instead of file names.
"""

import json
from pathlib import Path

from legal_rag.ingestion.models import DocumentRecord


def load_titles(manifest_path: Path) -> dict[str, str]:
    """Map local filename -> short display title from the dataset manifest."""
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text())
    titles: dict[str, str] = {}
    for doc in manifest.get("documents", []):
        title = doc.get("display_name") or doc.get("case_name") or doc.get("title", "")
        titles[doc["local_filename"]] = title
    return titles


def load_documents(processed_dir: Path, manifest_path: Path) -> list[tuple[DocumentRecord, str]]:
    """Load every processed record, paired with its display title."""
    titles = load_titles(manifest_path)
    documents: list[tuple[DocumentRecord, str]] = []
    for path in sorted(processed_dir.glob("*.json")):
        record = DocumentRecord.model_validate_json(path.read_text())
        title = titles.get(record.source.file_name, record.source.file_name)
        documents.append((record, title))
    return documents
