from legal_rag.evaluation.models import GoldDataset, GoldQuestion, QuestionEvaluation
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

    def ask(self, question: str, *, k: int, max_completion_tokens=None):
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
    assert [result.model_dump() for result in report.question_results] == [
        {
            "question_id": "q1",
            "retrieval_hit": True,
            "citation_count": 1,
            "citation_provenance_valid": True,
            "failure_reason": None,
        }
    ]


def test_evaluator_records_missing_citations_by_question() -> None:
    class _UngroundedService(_Service):
        def ask(self, question: str, *, k: int, max_completion_tokens=None):
            return Answer(question=question, text="Answer.", grounded=False, citations=[])

    dataset = GoldDataset(
        benchmark_version="test-v1",
        questions=[
            GoldQuestion(question_id="q1", question="Question", expected_document_ids=["a" * 64])
        ],
    )

    report = evaluate(_UngroundedService(), dataset, k=3)  # type: ignore[arg-type]

    assert report.question_results[0].failure_reason == "no_citations"
    assert report.question_results[0].citation_provenance_valid is False


def test_evaluator_resumes_completed_question_diagnostics() -> None:
    dataset = GoldDataset(
        benchmark_version="test-v1",
        questions=[
            GoldQuestion(question_id="q1", question="Question 1", expected_document_ids=["a" * 64]),
            GoldQuestion(question_id="q2", question="Question 2", expected_document_ids=["a" * 64]),
        ],
    )
    checkpoints = []

    report = evaluate(
        _Service(),  # type: ignore[arg-type]
        dataset,
        initial_question_results=[
            QuestionEvaluation(
                question_id="q1",
                retrieval_hit=True,
                citation_count=1,
                citation_provenance_valid=True,
            )
        ],
        on_question_complete=checkpoints.append,
    )

    assert [result.question_id for result in report.question_results] == ["q1", "q2"]
    assert len(checkpoints) == 1
    assert [result.question_id for result in checkpoints[0]] == ["q1", "q2"]


def test_evaluator_records_wrong_expected_source_as_retrieval_miss() -> None:
    dataset = GoldDataset(
        benchmark_version="test-v1",
        questions=[
            GoldQuestion(question_id="q1", question="Question", expected_document_ids=["b" * 64])
        ],
    )

    report = evaluate(_Service(), dataset, k=3)  # type: ignore[arg-type]

    assert report.metrics is not None
    assert report.metrics.retrieval_hit_rate_at_k == 0
    assert report.metrics.citation_provenance_validity == 1
    assert report.question_results[0].retrieval_hit is False
    assert report.question_results[0].citation_provenance_valid is True
