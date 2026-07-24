from types import SimpleNamespace

import pytest

from legal_rag.rag.azure_search import AzureAISearchStore
from legal_rag.rag.models import Chunk


def _chunk(chunk_id: str = "c1") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="d1",
        document_title="Case",
        section_path=["I. Analysis"],
        page_start=1,
        page_end=1,
        element_ids=["p1"],
        chunk_type="text",
        text="The legal text.",
        embed_text="Case I. Analysis The legal text.",
    )


class _FakeSearchClient:
    def __init__(self) -> None:
        self.uploaded: list[dict] = []
        self.search_calls: list[dict] = []

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        if kwargs["search_text"] == "*":
            return []
        return [
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "document_title": "Case",
                "section_path": ["I. Analysis"],
                "page_start": 1,
                "page_end": 1,
                "element_ids": ["p1"],
                "chunk_type": "text",
                "text": "The legal text.",
                "embed_text": "Case I. Analysis The legal text.",
                "@search.score": 1.2,
            }
        ]

    def upload_documents(self, *, documents: list[dict]):
        self.uploaded.extend(documents)
        return [
            SimpleNamespace(succeeded=True, key=document["chunk_id"], error_message=None)
            for document in documents
        ]

    def delete_documents(self, *, documents: list[dict]):
        return [SimpleNamespace(succeeded=True) for _ in documents]

    def get_document_count(self) -> int:
        return 1


@pytest.fixture
def store() -> tuple[AzureAISearchStore, _FakeSearchClient]:
    client = _FakeSearchClient()
    return (
        AzureAISearchStore(
            endpoint="https://example.search.windows.net",
            index_name="legal-rag",
            source_locations_enabled=True,
            search_client=client,  # type: ignore[arg-type]
        ),
        client,
    )


def test_indexes_chunks_with_vectors(store: tuple[AzureAISearchStore, _FakeSearchClient]) -> None:
    backend, client = store
    chunk = _chunk().model_copy(
        update={"source_anchor": "article-i", "source_start": 10, "source_end": 30}
    )
    backend.index([chunk], [[0.1, 0.2]])

    assert client.uploaded[0]["chunk_id"] == "c1"
    assert client.uploaded[0]["embedding"] == [0.1, 0.2]
    assert client.uploaded[0]["source_anchor"] == "article-i"
    assert client.uploaded[0]["source_start"] == 10
    assert client.uploaded[0]["source_end"] == 30


def test_hybrid_search_maps_results_to_chunks(
    store: tuple[AzureAISearchStore, _FakeSearchClient],
) -> None:
    backend, client = store

    results = backend.search(query_text="legal", query_vector=[0.1, 0.2], k=3)

    assert results[0].chunk.chunk_id == "c1"
    assert results[0].score == 1.2
    assert client.search_calls[-1]["search_text"] == "legal"
    assert client.search_calls[-1]["vector_queries"][0].fields == "embedding"


def test_rejects_mismatched_vectors(store: tuple[AzureAISearchStore, _FakeSearchClient]) -> None:
    backend, _ = store
    with pytest.raises(ValueError, match="same length"):
        backend.index([_chunk()], [])
