"""CLI: build the retrieval index from processed documents.

Usage: `legal-rag-index`
"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

from legal_rag.ingestion.logging_config import configure_logging, get_logger
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.backends import build_retrieval_backend
from legal_rag.rag.chunking import chunk_document, validate_embedding_payloads
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.corpus import load_documents


class EmbeddingCheckpoint:
    """A local, validated resume point for an expensive release embedding run.

    The checkpoint is operator-supplied and deliberately kept outside the
    repository. It is JSON rather than pickle so resuming a release never
    deserializes executable data.
    """

    _SCHEMA_VERSION = 1

    def __init__(self, path: Path, texts: list[str]) -> None:
        self._path = path
        self._fingerprint = hashlib.sha256("\0".join(texts).encode()).hexdigest()
        self._last_saved_count = 0

    def load(self) -> list[list[float]]:
        if not self._path.exists():
            return []
        with gzip.open(self._path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema_version") != self._SCHEMA_VERSION:
            raise RuntimeError("embedding checkpoint schema is unsupported")
        if payload.get("text_fingerprint") != self._fingerprint:
            raise RuntimeError("embedding checkpoint does not match this corpus build")
        vectors = payload.get("vectors")
        if not isinstance(vectors, list) or not all(isinstance(vector, list) for vector in vectors):
            raise RuntimeError("embedding checkpoint has an invalid vector payload")
        self._last_saved_count = len(vectors)
        return vectors

    def save(self, vectors: list[list[float]], *, force: bool = False) -> None:
        # Saving periodically limits I/O while losing at most 160 vectors
        # after an interrupted release.
        if not force and len(vectors) - self._last_saved_count < 160:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        payload = {
            "schema_version": self._SCHEMA_VERSION,
            "text_fingerprint": self._fingerprint,
            "vectors": vectors,
        }
        with gzip.open(temporary_path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        os.replace(temporary_path, self._path)
        self._last_saved_count = len(vectors)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the configured retrieval index")
    parser.add_argument(
        "--embedding-checkpoint",
        type=Path,
        help="gzip JSON checkpoint path for resumable Azure OpenAI embedding runs",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    logger = get_logger(__name__)

    try:
        args = _parse_args(argv)
        settings = get_rag_settings()
        documents = load_documents(settings.processed_dir, settings.dataset_manifest_path)
        if not documents:
            print(f"No processed documents found in {settings.processed_dir}", file=sys.stderr)
            return 1

        chunks = []
        for record, title in documents:
            document_chunks = chunk_document(
                record, title=title, max_chars=settings.chunk_max_chars
            )
            chunks.extend(document_chunks)
            print(f"  {title}: {len(document_chunks)} chunks ({record.page_count} pages)")

        validate_embedding_payloads(chunks)

        client = AzureOpenAIClient(settings)
        print(f"Embedding {len(chunks)} chunks via Azure OpenAI ...")
        texts = [chunk.embed_text for chunk in chunks]
        checkpoint = (
            EmbeddingCheckpoint(args.embedding_checkpoint, texts)
            if args.embedding_checkpoint is not None
            else None
        )
        initial_vectors = checkpoint.load() if checkpoint is not None else []
        if initial_vectors:
            print(f"Resuming from {len(initial_vectors)} checkpointed embeddings ...")
        vectors = client.embed(
            texts,
            initial_vectors=initial_vectors,
            on_batch_complete=(checkpoint.save if checkpoint is not None else None),
        )
        if checkpoint is not None:
            checkpoint.save(vectors, force=True)

        store = build_retrieval_backend(settings)
        store.index(chunks, vectors)
        logger.info(
            "index built",
            extra={"documents": len(documents), "chunks": len(chunks)},
        )
        print(f"Indexed {store.count()} chunks from {len(documents)} document(s).")
        return 0
    except Exception:
        logger.exception("index build failed")
        print("Index build failed; see logs for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
