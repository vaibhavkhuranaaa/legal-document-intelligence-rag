from pathlib import Path

from legal_rag.rag.answer import AnswerService
from legal_rag.rag.models import Chunk, ScoredChunk
from legal_rag.rag.source_registry import SourceRegistry
from legal_rag.rag.store import RetrievalBackend, reciprocal_rank_fusion


def _chunk(chunk_id: str, text: str = "Some legal text.") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="d" * 64,
        document_title="Abraham v. Estate of Wirtz (2025)",
        section_path=["II. ANALYSIS", "A. Disclosure"],
        page_start=11,
        page_end=12,
        element_ids=["p1"],
        chunk_type="text",
        text=text,
        embed_text=text,
    )


class _FakeStore(RetrievalBackend):
    def __init__(self, results: list[ScoredChunk]) -> None:
        self._results = results

    def index(self, chunks, vectors) -> None:
        raise NotImplementedError

    def search(self, *, query_text, query_vector, k) -> list[ScoredChunk]:
        return self._results[:k]

    def count(self) -> int:
        return len(self._results)


class _FakeClient:
    def __init__(self, completion: str) -> None:
        self._completion = completion
        self.last_user_prompt: str | None = None

    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def complete(self, *, system: str, user: str) -> str:
        self.last_user_prompt = user
        return self._completion


def test_rrf_prefers_ids_ranked_high_in_both_lists() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])

    ids = [chunk_id for chunk_id, _ in fused]
    assert ids[0] in {"a", "b"}
    assert set(ids) == {"a", "b", "c", "d"}
    assert fused[0][1] > fused[-1][1]


def test_answer_resolves_cited_markers_to_citations() -> None:
    store = _FakeStore([ScoredChunk(chunk=_chunk(f"c{i}"), score=1.0) for i in range(1, 4)])
    client = _FakeClient("The notice was adequate [1]. The demand failed [3].")
    service = AnswerService(client, store)  # type: ignore[arg-type]

    answer = service.ask("Was the notice adequate?")

    assert answer.grounded is True
    assert [c.marker for c in answer.citations] == [1, 3]
    assert answer.citations[0].chunk_id == "c1"
    assert answer.citations[1].chunk_id == "c3"
    assert "p. 11" in answer.citations[0].display or "pp. 11–12" in answer.citations[0].display


def test_answer_marks_ungrounded_when_no_markers_cited() -> None:
    store = _FakeStore([ScoredChunk(chunk=_chunk("c1"), score=1.0)])
    client = _FakeClient("I believe the answer is yes, based on general knowledge.")
    service = AnswerService(client, store)  # type: ignore[arg-type]

    answer = service.ask("Question?")

    assert answer.grounded is False
    assert answer.citations == []


def test_answer_marks_ungrounded_on_insufficient_evidence_response() -> None:
    store = _FakeStore([ScoredChunk(chunk=_chunk("c1"), score=1.0)])
    client = _FakeClient(
        "The provided documents do not contain enough information to answer this question. [1]"
    )
    service = AnswerService(client, store)  # type: ignore[arg-type]

    answer = service.ask("Unanswerable question?")

    assert answer.grounded is False


def test_answer_handles_empty_index() -> None:
    store = _FakeStore([])
    client = _FakeClient("irrelevant")
    service = AnswerService(client, store)  # type: ignore[arg-type]

    answer = service.ask("Question?")

    assert answer.grounded is False
    assert "index is empty" in answer.text


def test_context_includes_document_titles_and_pages() -> None:
    store = _FakeStore([ScoredChunk(chunk=_chunk("c1"), score=1.0)])
    client = _FakeClient("Answer [1].")
    service = AnswerService(client, store)  # type: ignore[arg-type]

    service.ask("Question?")

    assert client.last_user_prompt is not None
    assert "Abraham v. Estate of Wirtz (2025)" in client.last_user_prompt
    assert "pages 11–12" in client.last_user_prompt


def test_out_of_range_markers_are_ignored() -> None:
    store = _FakeStore([ScoredChunk(chunk=_chunk("c1"), score=1.0)])
    client = _FakeClient("Answer [1] and hallucinated [9].")
    service = AnswerService(client, store)  # type: ignore[arg-type]

    answer = service.ask("Question?")

    assert [c.marker for c in answer.citations] == [1]


def test_answer_resolves_public_source_provenance() -> None:
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))
    chunk = _chunk("c1")
    chunk.document_id = registry.documents[0].document_id
    store = _FakeStore([ScoredChunk(chunk=chunk, score=1.0)])
    service = AnswerService(_FakeClient("Answer [1]."), store, registry)  # type: ignore[arg-type]

    citation = service.ask("Question?").citations[0]

    assert citation.source_checksum == registry.documents[0].document_id
    assert citation.source_url is not None
    assert citation.source_url.endswith("#page=11")
