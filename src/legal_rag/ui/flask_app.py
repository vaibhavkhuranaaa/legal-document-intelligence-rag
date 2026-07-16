"""Flask research workspace for the public legal-document corpus."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from flask import Flask, abort, render_template, request

from legal_rag.evaluation.models import EvaluationReport
from legal_rag.rag.answer import AnswerService
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.backends import build_retrieval_backend
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.models import Answer, Citation, ScoredChunk
from legal_rag.rag.source_registry import SourceRegistry

_MAX_QUESTION_LENGTH = 2_000
_DEFAULT_EVALUATION_REPORT = Path("data/evaluation/latest.json")


@dataclass(frozen=True)
class EvidenceMatch:
    """A query-relative retrieval signal for one displayed passage."""

    result: ScoredChunk
    citation: Citation
    score: int
    tier: str


@dataclass(frozen=True)
class AnswerMatch:
    """Plain-language verification of the sources shown with an answer."""

    score: int
    cited_source_count: int
    detail: str


def build_evidence_matches(
    results: list[tuple[ScoredChunk, Citation]],
) -> list[EvidenceMatch]:
    """Normalize retrieved scores within one result set, never as certainty."""
    if not results:
        return []
    top_score = max(result.score for result, _ in results)
    denominator = top_score if top_score > 0 else 1.0
    matches: list[EvidenceMatch] = []
    for result, citation in results:
        score = round(min(100, max(0, result.score / denominator * 100)))
        tier = "Top match" if score >= 90 else "Strong match" if score >= 70 else "Supporting match"
        matches.append(EvidenceMatch(result=result, citation=citation, score=score, tier=tier))
    return matches


def build_answer_match(answer: Answer) -> AnswerMatch:
    """Report whether displayed citations resolve to official public sources.

    This verifies source links only. It is not a legal-correctness score and
    must not be presented as one.
    """
    cited_source_count = sum(citation.source_url is not None for citation in answer.citations)
    if not answer.grounded or not answer.citations:
        return AnswerMatch(
            score=0,
            cited_source_count=0,
            detail="No supporting source was identified for this response.",
        )
    score = round(cited_source_count / len(answer.citations) * 100)
    detail = (
        "Every cited source links to the public record."
        if score == 100
        else "Some cited sources do not have a public link."
    )
    return AnswerMatch(score=score, cited_source_count=cited_source_count, detail=detail)


class _Workspace:
    def __init__(
        self,
        registry: SourceRegistry,
        service_factory: Callable[[SourceRegistry], tuple[AnswerService, int]],
    ) -> None:
        self.registry = registry
        self._service_factory = service_factory

    @cached_property
    def service_and_count(self) -> tuple[AnswerService, int]:
        return self._service_factory(self.registry)

    def service(self) -> AnswerService:
        return self.service_and_count[0]

    def chunk_count(self) -> int:
        return self.service_and_count[1]


def _build_service(registry: SourceRegistry) -> tuple[AnswerService, int]:
    settings = get_rag_settings()
    store = build_retrieval_backend(settings)
    return AnswerService(AzureOpenAIClient(settings), store, registry), store.count()


def create_app(
    *,
    registry: SourceRegistry | None = None,
    service_factory: Callable[[SourceRegistry], tuple[AnswerService, int]] = _build_service,
    evaluation_report_path: Path = _DEFAULT_EVALUATION_REPORT,
) -> Flask:
    """Create the read-only public research application."""
    registry = registry or SourceRegistry.load(Path("data/dataset_manifest.json"))
    workspace = _Workspace(registry, service_factory)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

    @app.template_filter("pages")
    def format_pages(citation: Citation) -> str:
        if citation.source_kind == "sec_html":
            return citation.section_path[-1] if citation.section_path else "HTML filing section"
        return (
            f"p. {citation.page_start}"
            if citation.page_start == citation.page_end
            else f"pp. {citation.page_start}-{citation.page_end}"
        )

    @app.template_filter("source_location")
    def format_source_location(citation: Citation) -> str:
        if citation.source_kind == "court_pdf":
            return format_pages(citation)
        section = citation.section_path[-1] if citation.section_path else "HTML filing section"
        if citation.source_start is not None and citation.source_end is not None:
            return f"{section}; text offsets {citation.source_start}-{citation.source_end}"
        return section

    def render_home(*, answer: Answer | None = None, error: str | None = None, question: str = ""):
        try:
            chunk_count = workspace.chunk_count()
        except Exception:
            chunk_count = None
            error = error or (
                "The research service is temporarily unavailable. Please try again shortly."
            )
        return render_template(
            "home.html",
            answer=answer,
            answer_match=build_answer_match(answer) if answer is not None else None,
            error=error,
            question=question,
            chunk_count=chunk_count,
            source_count=len(workspace.registry.documents),
        )

    @app.get("/")
    def home():
        return render_home(question=request.args.get("q", "").strip())

    @app.post("/ask")
    def ask():
        question = request.form.get("question", "").strip()
        if not question:
            return render_home(error="Enter a research question to search the public record."), 400
        if len(question) > _MAX_QUESTION_LENGTH:
            return (
                render_home(
                    error="Keep research questions under 2,000 characters.", question=question
                ),
                400,
            )
        try:
            answer = workspace.service().ask(question)
        except Exception:
            return render_home(
                error="The research service is temporarily unavailable. Please try again shortly.",
                question=question,
            ), 503
        return render_home(answer=answer, question=question)

    @app.get("/evidence")
    def evidence():
        question = request.args.get("q", "").strip()
        matches: list[EvidenceMatch] = []
        error = None
        if question:
            if len(question) > _MAX_QUESTION_LENGTH:
                abort(400)
            try:
                results = [
                    (result, workspace.service().citation_for(index, result))
                    for index, result in enumerate(workspace.service().retrieve(question), start=1)
                ]
                matches = build_evidence_matches(results)
            except Exception:
                error = "Source search is temporarily unavailable. Please try again shortly."
        return render_template("evidence.html", question=question, matches=matches, error=error)

    @app.get("/corpus")
    def corpus():
        source_type = request.args.get("source_type", "")
        company = request.args.get("company", "")
        form_type = request.args.get("form", "")
        court = request.args.get("court", "")
        year = request.args.get("year", "")
        topic = request.args.get("topic", "")
        documents = workspace.registry.documents
        if source_type:
            documents = [document for document in documents if document.source_kind == source_type]
        if company:
            documents = [document for document in documents if document.company_name == company]
        if form_type:
            documents = [document for document in documents if document.form_type == form_type]
        if court:
            documents = [document for document in documents if document.court == court]
        if year:
            documents = [document for document in documents if str(document.year) == year]
        if topic:
            documents = [document for document in documents if document.legal_topic == topic]
        return render_template(
            "corpus.html",
            documents=documents,
            source_types=sorted(
                {document.source_kind for document in workspace.registry.documents}
            ),
            companies=sorted(
                {
                    document.company_name
                    for document in workspace.registry.documents
                    if document.company_name
                }
            ),
            form_types=sorted(
                {
                    document.form_type
                    for document in workspace.registry.documents
                    if document.form_type
                }
            ),
            courts=sorted({document.court for document in workspace.registry.documents}),
            years=sorted(
                {document.year for document in workspace.registry.documents}, reverse=True
            ),
            topics=sorted({document.legal_topic for document in workspace.registry.documents}),
            selected_court=court,
            selected_year=year,
            selected_topic=topic,
            selected_source_type=source_type,
            selected_company=company,
            selected_form_type=form_type,
        )

    @app.get("/evaluation")
    def evaluation():
        report = _load_evaluation_report(evaluation_report_path)
        return render_template("evaluation.html", report=report)

    @app.get("/how-it-works")
    def how_it_works():
        return render_template("how_it_works.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "legal-document-intelligence"}

    return app


def _load_evaluation_report(path: Path) -> EvaluationReport:
    return EvaluationReport.model_validate(json.loads(path.read_text()))


app = create_app()
