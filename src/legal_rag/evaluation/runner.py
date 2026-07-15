"""Evaluation runner for retrieval coverage and citation provenance."""

from datetime import UTC, datetime
from urllib.parse import urlsplit

from legal_rag.evaluation.models import EvaluationMetrics, EvaluationReport, GoldDataset
from legal_rag.rag.answer import AnswerService
from legal_rag.rag.models import Citation


def load_gold_dataset(path) -> GoldDataset:
    return GoldDataset.model_validate_json(path.read_text())


def evaluate(service: AnswerService, dataset: GoldDataset, *, k: int = 8) -> EvaluationReport:
    """Run the versioned benchmark against the configured retrieval backend."""
    retrieval_hits = 0
    valid_citation_questions = 0
    for item in dataset.questions:
        evidence = service.retrieve(item.question, k=k)
        if any(result.chunk.document_id in item.expected_document_ids for result in evidence):
            retrieval_hits += 1
        answer = service.ask(item.question, k=k)
        if answer.citations and all(_citation_is_valid(citation) for citation in answer.citations):
            valid_citation_questions += 1

    question_count = len(dataset.questions)
    return EvaluationReport(
        status="complete",
        benchmark_version=dataset.benchmark_version,
        corpus_document_count=len({
            document_id
            for item in dataset.questions
            for document_id in item.expected_document_ids
        }),
        question_count=question_count,
        retrieval_k=k,
        generated_at=datetime.now(UTC),
        metrics=EvaluationMetrics(
            retrieval_hit_rate_at_k=retrieval_hits / question_count,
            citation_provenance_validity=valid_citation_questions / question_count,
        ),
        note=(
            "Results are generated against the configured production index. "
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
