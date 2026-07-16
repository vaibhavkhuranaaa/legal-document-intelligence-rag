from types import SimpleNamespace

import httpx
from openai import APIConnectionError

from legal_rag.rag.azure_openai import (
    AzureOpenAIClient,
    _connection_retry_wait_seconds,
    _rate_limit_wait_seconds,
)


class _EmbeddingClient:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []
        self.embeddings = self

    def create(self, *, model: str, input: list[str]):  # noqa: A002
        self.batches.append(input)
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[float(index)])
                for index in range(len(input))
            ]
        )


def test_embedding_client_uses_release_safe_batches() -> None:
    sdk_client = _EmbeddingClient()
    settings = SimpleNamespace(azure_openai_embedding_deployment="embedding-test")
    client = AzureOpenAIClient(settings, sdk_client=sdk_client)  # type: ignore[arg-type]

    vectors = client.embed([str(index) for index in range(9)])

    assert [len(batch) for batch in sdk_client.batches] == [8, 1]
    assert vectors == [[float(index)] for index in range(8)] + [[0.0]]


def test_embedding_resumes_after_checkpointed_vectors(monkeypatch) -> None:
    monkeypatch.setattr("legal_rag.rag.azure_openai.time.sleep", lambda _: None)
    sdk_client = _EmbeddingClient()
    settings = SimpleNamespace(azure_openai_embedding_deployment="embedding-test")
    completed_counts: list[int] = []

    vectors = AzureOpenAIClient(settings, sdk_client=sdk_client).embed(
        [str(index) for index in range(10)],
        initial_vectors=[[99.0]] * 8,
        on_batch_complete=lambda completed: completed_counts.append(len(completed)),
    )

    assert sdk_client.batches == [["8", "9"]]
    assert completed_counts == [10]
    assert vectors[:8] == [[99.0]] * 8
    assert vectors[8:] == [[0.0], [1.0]]


def test_rate_limit_wait_prefers_server_hint() -> None:
    error = SimpleNamespace(response=SimpleNamespace(headers={"retry-after-ms": "1500"}))

    assert _rate_limit_wait_seconds(error) == 1.5  # type: ignore[arg-type]


def test_embedding_retries_a_transient_connection_drop(monkeypatch) -> None:
    class _FlakyEmbeddingClient(_EmbeddingClient):
        def __init__(self) -> None:
            super().__init__()
            self._failed_once = False

        def create(self, *, model: str, input: list[str]):  # noqa: A002
            if not self._failed_once:
                self._failed_once = True
                raise APIConnectionError(request=httpx.Request("POST", "https://example.test"))
            return super().create(model=model, input=input)

    monkeypatch.setattr("legal_rag.rag.azure_openai.time.sleep", lambda _: None)
    sdk_client = _FlakyEmbeddingClient()
    settings = SimpleNamespace(azure_openai_embedding_deployment="embedding-test")

    vectors = AzureOpenAIClient(settings, sdk_client=sdk_client).embed(["one"])

    assert vectors == [[0.0]]
    assert _connection_retry_wait_seconds(0) == 5.0
