"""Evaluation runner for retrieval coverage and citation provenance."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from legal_rag.evaluation.models import (
    EvaluationMetrics,
    EvaluationReport,
    GoldDataset,
    QuestionEvaluation,
)
from legal_rag.rag.answer import AnswerService
from legal_rag.rag.models import Citation


def load_gold_dataset(path) -> GoldDataset:
    return GoldDataset.model_validate_json(path.read_text())


def evaluate(
    service: AnswerService,
    dataset: GoldDataset,
    *,
    k: int = 8,
    answer_max_completion_tokens: int | None = None,
    chat_request_interval_seconds: float = 0.0,
    initial_question_results: list[QuestionEvaluation] | None = None,
    on_question_complete: Callable[[list[QuestionEvaluation]], None] | None = None,
) -> EvaluationReport:
    """Run the versioned benchmark, resuming completed non-content diagnostics."""
    if chat_request_interval_seconds < 0:
        raise ValueError("chat_request_interval_seconds must not be negative")
    known_question_ids = {item.question_id for item in dataset.questions}
    question_results_by_id = {
        result.question_id: result for result in initial_question_results or []
    }
    if len(question_results_by_id) != len(initial_question_results or []):
        raise ValueError("initial_question_results must not contain duplicate question IDs")
    unknown_question_ids = set(question_results_by_id) - known_question_ids
    if unknown_question_ids:
        raise ValueError("initial_question_results contain IDs absent from the gold dataset")

    for index, item in enumerate(dataset.questions):
        if item.question_id in question_results_by_id:
            continue
        evidence = service.retrieve(item.question, k=k)
        retrieval_hit = any(
            result.chunk.document_id in item.expected_document_ids for result in evidence
        )
        answer = service.ask(item.question, k=k, max_completion_tokens=answer_max_completion_tokens)
        citation_provenance_valid = bool(answer.citations) and all(
            _citation_is_valid(citation) for citation in answer.citations
        )
        question_results_by_id[item.question_id] = QuestionEvaluation(
            question_id=item.question_id,
            retrieval_hit=retrieval_hit,
            citation_count=len(answer.citations),
            citation_provenance_valid=citation_provenance_valid,
            failure_reason=(
                None
                if citation_provenance_valid
                else "no_citations"
                if not answer.citations
                else "invalid_citation_provenance"
            ),
        )
        question_results = [
            question_results_by_id[question.question_id]
            for question in dataset.questions
            if question.question_id in question_results_by_id
        ]
        if on_question_complete is not None:
            on_question_complete(question_results)
        if index < len(dataset.questions) - 1:
            time.sleep(chat_request_interval_seconds)

    question_results = [question_results_by_id[item.question_id] for item in dataset.questions]
    retrieval_hits = sum(result.retrieval_hit for result in question_results)
    valid_citation_questions = sum(result.citation_provenance_valid for result in question_results)
    question_count = len(dataset.questions)
    return EvaluationReport(
        status="complete",
        benchmark_version=dataset.benchmark_version,
        corpus_document_count=len(
            {
                document_id
                for item in dataset.questions
                for document_id in item.expected_document_ids
            }
        ),
        question_count=question_count,
        retrieval_k=k,
        generated_at=datetime.now(UTC),
        metrics=EvaluationMetrics(
            retrieval_hit_rate_at_k=retrieval_hits / question_count,
            citation_provenance_validity=valid_citation_questions / question_count,
        ),
        question_results=question_results,
        note=(
            "Results are generated against the configured retrieval index. "
            "They are not a legal-accuracy claim or legal advice."
        ),
    )


def _citation_is_valid(citation: Citation) -> bool:
    parsed = urlsplit(citation.source_url or "")
    checksum = citation.source_checksum or ""
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and len(checksum) == 64
        and all(character in "0123456789abcdef" for character in checksum.lower())
        and citation.page_start >= 1
        and citation.page_end >= citation.page_start
    )
