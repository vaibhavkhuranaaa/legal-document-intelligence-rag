from types import SimpleNamespace

from legal_rag.rag.azure_openai import AzureOpenAIClient


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
