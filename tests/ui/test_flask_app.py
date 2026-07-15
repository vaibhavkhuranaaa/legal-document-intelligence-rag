from pathlib import Path

from legal_rag.rag.models import Answer, Chunk, Citation, ScoredChunk
from legal_rag.rag.source_registry import SourceRegistry
from legal_rag.ui.flask_app import create_app


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
    assert client.get("/healthz").get_json()["status"] == "ok"


def test_answer_and_evidence_expose_page_aware_source_link() -> None:
    client = _client()

    answer = client.post("/ask", data={"question": "What does the record say?"})
    evidence = client.get("/evidence?q=What+does+the+record+say%3F")

    assert answer.status_code == 200
    assert b"Open original opinion" in answer.data
    assert b"#page=2" in answer.data
    assert evidence.status_code == 200
    assert b"Source checksum" in evidence.data


def test_empty_question_is_rejected() -> None:
    response = _client().post("/ask", data={"question": "  "})

    assert response.status_code == 400
    assert b"Enter a research question" in response.data
