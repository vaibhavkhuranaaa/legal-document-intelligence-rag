"""Azure AI Search production retrieval backend.

The Azure index is provisioned separately with fields matching `_SELECT_FIELDS`.
This class owns document replacement and hybrid querying, but never creates a
service or index as a side effect.
"""

from collections.abc import Iterable

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from legal_rag.rag.models import Chunk, ScoredChunk
from legal_rag.rag.store import RetrievalBackend

_VECTOR_FIELD = "embedding"
_BATCH_SIZE = 100
_SELECT_FIELDS = [
    "chunk_id",
    "document_id",
    "document_title",
    "section_path",
    "page_start",
    "page_end",
    "element_ids",
    "chunk_type",
    "text",
    "embed_text",
]


class AzureAISearchStore(RetrievalBackend):
    """Hybrid Azure AI Search backend using text and vector queries together."""

    def __init__(
        self,
        *,
        endpoint: str,
        index_name: str,
        source_locations_enabled: bool = False,
        search_client: SearchClient | None = None,
    ) -> None:
        self._search_client = search_client or SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=DefaultAzureCredential(),
        )
        self._source_locations_enabled = source_locations_enabled

    @property
    def _select_fields(self) -> list[str]:
        location_fields = ["source_anchor", "source_start", "source_end"]
        if self._source_locations_enabled:
            return [*_SELECT_FIELDS, *location_fields]
        return _SELECT_FIELDS

    def index(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        self._delete_all()
        documents = [
            self._to_document(chunk, vector, self._source_locations_enabled)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        for batch in _batches(documents, _BATCH_SIZE):
            results = self._search_client.upload_documents(documents=batch)
            failures = [result for result in results if not result.succeeded]
            if failures:
                messages = ", ".join(f"{result.key}: {result.error_message}" for result in failures)
                raise RuntimeError(f"Azure AI Search indexing failed: {messages}")

    def search(self, *, query_text: str, query_vector: list[float], k: int) -> list[ScoredChunk]:
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=k,
            fields=_VECTOR_FIELD,
        )
        results = self._search_client.search(
            search_text=query_text,
            vector_queries=[vector_query],
            select=self._select_fields,
            top=k,
        )
        return [
            ScoredChunk(chunk=self._to_chunk(result), score=float(result.get("@search.score", 0.0)))
            for result in results
        ]

    def count(self) -> int:
        return self._search_client.get_document_count()

    def _delete_all(self) -> None:
        existing = self._search_client.search(search_text="*", select=["chunk_id"], top=1000)
        ids = [{"chunk_id": result["chunk_id"]} for result in existing]
        for batch in _batches(ids, _BATCH_SIZE):
            results = self._search_client.delete_documents(documents=batch)
            failures = [result for result in results if not result.succeeded]
            if failures:
                raise RuntimeError("Azure AI Search could not clear the existing index")

    @staticmethod
    def _to_document(chunk: Chunk, vector: list[float], source_locations_enabled: bool) -> dict:
        document = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "document_title": chunk.document_title,
            "section_path": chunk.section_path,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "element_ids": chunk.element_ids,
            "chunk_type": chunk.chunk_type,
            "text": chunk.text,
            "embed_text": chunk.embed_text,
            _VECTOR_FIELD: vector,
        }
        if source_locations_enabled:
            document.update(
                {
                    "source_anchor": chunk.source_anchor,
                    "source_start": chunk.source_start,
                    "source_end": chunk.source_end,
                }
            )
        return document

    @staticmethod
    def _to_chunk(result: dict) -> Chunk:
        return Chunk(
            chunk_id=result["chunk_id"],
            document_id=result["document_id"],
            document_title=result["document_title"],
            section_path=result["section_path"],
            page_start=result["page_start"],
            page_end=result["page_end"],
            source_anchor=result.get("source_anchor"),
            source_start=result.get("source_start"),
            source_end=result.get("source_end"),
            element_ids=result["element_ids"],
            chunk_type=result["chunk_type"],
            text=result["text"],
            embed_text=result["embed_text"],
        )


def _batches(items: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
