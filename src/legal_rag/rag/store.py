"""Hybrid retrieval store: Chroma (vector) + BM25 (lexical), RRF-fused.

`RetrievalBackend` is the seam for the future Azure AI Search production
implementation (architecture review §7) — mirroring the `StorageBackend`
pattern (ADR-0005). The dev implementation runs hybrid search locally:
dense retrieval via a persistent Chroma collection, lexical retrieval via
BM25 over the same chunks, fused with reciprocal rank fusion. Legal queries
are exact-term-heavy (docket numbers, statute cites, defined terms), which
is why the lexical leg is not optional.
"""

import re
from abc import ABC, abstractmethod

import chromadb

from legal_rag.rag.models import Chunk, ScoredChunk

_COLLECTION_NAME = "legal_rag_chunks"
_RRF_K = 60
_TOKEN_PATTERN = re.compile(r"[a-z0-9§]+(?:[.\-()][a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def reciprocal_rank_fusion(
    rankings: list[list[str]], *, k: int = _RRF_K
) -> list[tuple[str, float]]:
    """Fuse multiple ranked ID lists into one, scored by summed 1/(k+rank)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class RetrievalBackend(ABC):
    @abstractmethod
    def index(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace the index contents with these chunks and their vectors."""

    @abstractmethod
    def search(self, *, query_text: str, query_vector: list[float], k: int) -> list[ScoredChunk]:
        """Hybrid-search the index; return the top-k fused results."""

    @abstractmethod
    def count(self) -> int:
        """Number of chunks currently indexed."""


class ChromaHybridStore(RetrievalBackend):
    """Local dev implementation: persistent Chroma + in-memory BM25."""

    def __init__(self, persist_dir: str) -> None:
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            _COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        self._chunks: dict[str, Chunk] = {}
        self._bm25 = None
        self._bm25_ids: list[str] = []
        self._load_existing()

    def _load_existing(self) -> None:
        existing = self._collection.get(include=["documents", "metadatas"])
        for chunk_id, metadata in zip(existing["ids"], existing["metadatas"], strict=True):
            self._chunks[chunk_id] = Chunk.model_validate_json(metadata["chunk_json"])
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        from rank_bm25 import BM25Okapi

        self._bm25_ids = list(self._chunks)
        if self._bm25_ids:
            corpus = [_tokenize(self._chunks[cid].text) for cid in self._bm25_ids]
            self._bm25 = BM25Okapi(corpus)
        else:
            self._bm25 = None

    def index(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        # Rebuild from scratch: the corpus is small and idempotent rebuilds
        # are simpler and safer than incremental upserts at this stage.
        self._client.delete_collection(_COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            _COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.embed_text for c in chunks],
            metadatas=[
                {"chunk_json": c.model_dump_json(), "document_id": c.document_id} for c in chunks
            ],
        )
        self._chunks = {c.chunk_id: c for c in chunks}
        self._rebuild_bm25()

    def search(self, *, query_text: str, query_vector: list[float], k: int) -> list[ScoredChunk]:
        if not self._chunks:
            return []
        pool = min(len(self._chunks), max(k * 3, 20))

        vector_result = self._collection.query(query_embeddings=[query_vector], n_results=pool)
        vector_ranking = vector_result["ids"][0]

        lexical_ranking: list[str] = []
        if self._bm25 is not None:
            scores = self._bm25.get_scores(_tokenize(query_text))
            ranked = sorted(zip(self._bm25_ids, scores, strict=True), key=lambda x: -x[1])
            lexical_ranking = [cid for cid, score in ranked[:pool] if score > 0]

        fused = reciprocal_rank_fusion([vector_ranking, lexical_ranking])
        return [
            ScoredChunk(chunk=self._chunks[chunk_id], score=score)
            for chunk_id, score in fused[:k]
            if chunk_id in self._chunks
        ]

    def count(self) -> int:
        return len(self._chunks)
