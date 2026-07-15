from legal_rag.evaluation.models import GoldDataset, GoldQuestion
from legal_rag.evaluation.runner import evaluate
from legal_rag.rag.models import Answer, Chunk, Citation, ScoredChunk


class _Service:
    def retrieve(self, question: str, *, k: int):
        return [
            ScoredChunk(
                chunk=Chunk(
                    chunk_id="chunk-1",
                    document_id="a" * 64,
                    document_title="Test opinion",
                    page_start=1,
                    page_end=1,
                    element_ids=["p1"],
                    chunk_type="text",
                    text="Evidence",
                    embed_text="Evidence",
                ),
                score=1.0,
            )
        ]

    def ask(self, question: str, *, k: int):
        return Answer(
            question=question,
            text="Answer [1].",
            grounded=True,
            citations=[
                Citation(
                    marker=1,
                    document_title="Test opinion",
                    section_path=[],
                    page_start=1,
                    page_end=1,
                    chunk_id="chunk-1",
                    snippet="Evidence",
                    source_url="https://courts.example/opinion.pdf#page=1",
                    source_checksum="a" * 64,
                )
            ],
        )


def test_evaluator_reports_retrieval_and_provenance_metrics() -> None:
    dataset = GoldDataset(
        benchmark_version="test-v1",
        questions=[
            GoldQuestion(question_id="q1", question="Question", expected_document_ids=["a" * 64])
        ],
    )

    report = evaluate(_Service(), dataset, k=3)  # type: ignore[arg-type]

    assert report.status == "complete"
    assert report.metrics is not None
    assert report.metrics.retrieval_hit_rate_at_k == 1
    assert report.metrics.citation_provenance_validity == 1
