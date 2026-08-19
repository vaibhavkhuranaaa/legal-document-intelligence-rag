from pathlib import Path

from legal_rag.rag.models import Answer, Chunk, Citation, ScoredChunk
from legal_rag.rag.source_registry import SourceRegistry
from legal_rag.ui.flask_app import build_answer_match, build_evidence_matches, create_app


class _FakeService:
    def __init__(self, registry: SourceRegistry) -> None:
        self._source = registry.documents[0]
        self._result = ScoredChunk(
            chunk=Chunk(
                chunk_id="chunk-1",
                document_id=self._source.document_id,
                document_title=self._source.display_name,
                section_path=["II. Analysis"],
                page_start=2,
                page_end=2,
                element_ids=["p1"],
                chunk_type="text",
                text="The public record contains this evidence.",
                embed_text="The public record contains this evidence.",
            ),
            score=0.9,
        )

    def _citation(self, marker: int) -> Citation:
        return Citation(
            marker=marker,
            document_title=self._source.display_name,
            section_path=["II. Analysis"],
            page_start=2,
            page_end=2,
            chunk_id="chunk-1",
            snippet="The public record contains this evidence.",
            source_url=self._source.source_page_url(2),
            source_checksum=self._source.document_id,
        )

    def ask(self, question: str) -> Answer:
        return Answer(
            question=question,
            text="Grounded answer [1].",
            citations=[self._citation(1)],
            grounded=True,
        )

    def retrieve(self, question: str):
        return [self._result]

    def citation_for(self, marker: int, result: ScoredChunk) -> Citation:
        return self._citation(marker)


def _client():
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))
    app = create_app(
        registry=registry,
        service_factory=lambda source_registry: (_FakeService(source_registry), 390),  # type: ignore[arg-type]
        evaluation_report_path=Path("data/evaluation/latest.json"),
    )
    app.config.update(TESTING=True)
    return app.test_client()


def test_public_workspace_routes_render() -> None:
    client = _client()

    assert client.get("/").status_code == 200
    assert client.get("/corpus").status_code == 200
    assert client.get("/evaluation").status_code == 200
    assert client.get("/how-it-works").status_code == 200
    assert client.get("/healthz").get_json()["status"] == "ok"
    assert b">Evaluation<" not in client.get("/").data
    assert b"Start an evidence review" in client.get("/evidence").data


def test_corpus_exposes_each_registered_official_source() -> None:
    registry = SourceRegistry.load(Path("data/dataset_manifest.json"))
    page = _client().get("/corpus")

    assert page.status_code == 200
    assert page.data.count(b"Open canonical court PDF") == sum(
        document.source_kind == "court_pdf" for document in registry.documents
    )
    assert page.data.count(b"Open official filing") == sum(
        document.source_kind == "sec_html" for document in registry.documents
    )
    for document in registry.documents:
        assert document.source_url.encode() in page.data


def test_answer_and_evidence_expose_page_aware_source_link() -> None:
    client = _client()

    answer = client.post("/ask", data={"question": "What does the record say?"})
    evidence = client.get("/evidence?q=What+does+the+record+say%3F")

    assert answer.status_code == 200
    assert b"Open original opinion" in answer.data
    assert b"#page=2" in answer.data
    assert evidence.status_code == 200
    assert b"Source checksum" in evidence.data
    assert b"CITATION LINKS / COMPLETE" in answer.data
    assert b"1</strong> of <strong>1</strong> cited record links" in answer.data
    assert b"Every cited source links to the public record." in answer.data
    assert b"SUPPORTED" not in answer.data
    assert b"/100" not in answer.data
    assert b"Source relevance" in evidence.data
    assert b"100<small>/100</small>" in evidence.data
    assert b"Top match" in evidence.data
    assert b"#evidence-1" in answer.data


def test_empty_question_is_rejected() -> None:
    response = _client().post("/ask", data={"question": "  "})

    assert response.status_code == 400
    assert b"Enter a research question" in response.data


def test_evidence_match_is_relative_to_the_returned_result_set() -> None:
    service = _FakeService(SourceRegistry.load(Path("data/dataset_manifest.json")))
    first = service.retrieve("question")[0]
    second = first.model_copy(update={"score": 0.45})

    matches = build_evidence_matches(
        [(first, service.citation_for(1, first)), (second, service.citation_for(2, second))]
    )

    assert [(match.score, match.tier) for match in matches] == [
        (100, "Top match"),
        (50, "Supporting match"),
    ]


def test_answer_match_verifies_public_source_links_without_claiming_correctness() -> None:
    answer = _FakeService(SourceRegistry.load(Path("data/dataset_manifest.json"))).ask("Question")

    match = build_answer_match(answer)

    assert match.score == 100
    assert match.cited_source_count == 1
    assert match.detail == "Every cited source links to the public record."


def test_home_includes_question_guidance_and_examples() -> None:
    page = _client().get("/")

    assert b"Ask one focused question at a time." in page.data
    assert b"Try an example:" in page.data
    assert b"Microsoft and Activision merger" in page.data
    assert b"Do not enter confidential or privileged information." in page.data
    assert b"data-character-count" in page.data
    assert b">Method<" in page.data


def test_answer_promotes_findings_and_compacts_the_query_workspace() -> None:
    page = _client().post("/ask", data={"question": "What does the record say?"})

    assert b"QUESTION ON RECORD" in page.data
    assert b"data-analysis-result" in page.data
    assert b"Ask another question" in page.data
    assert b"Research the record" not in page.data
    assert b"Collection register" not in page.data


def test_public_pages_do_not_expose_technical_or_ai_product_language() -> None:
    client = _client()
    pages = [
        client.get("/").data,
        client.get("/corpus").data,
        client.get("/evaluation").data,
        client.get("/how-it-works").data,
        client.get("/evidence?q=What+does+the+record+say%3F").data,
    ]

    for page in pages:
        assert b"RAG" not in page
        assert b"generated" not in page.lower()
        assert b"chunk" not in page.lower()
        assert "—".encode() not in page
