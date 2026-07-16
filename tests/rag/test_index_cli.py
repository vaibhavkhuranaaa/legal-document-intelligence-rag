import gzip

import pytest

from legal_rag.rag.index_cli import EmbeddingCheckpoint


def test_embedding_checkpoint_round_trips_matching_vectors(tmp_path) -> None:
    path = tmp_path / "release-embeddings.json.gz"
    checkpoint = EmbeddingCheckpoint(path, ["first", "second"])

    checkpoint.save([[0.1, 0.2], [0.3, 0.4]], force=True)

    assert EmbeddingCheckpoint(path, ["first", "second"]).load() == [[0.1, 0.2], [0.3, 0.4]]


def test_embedding_checkpoint_rejects_a_different_corpus(tmp_path) -> None:
    path = tmp_path / "release-embeddings.json.gz"
    EmbeddingCheckpoint(path, ["first"]).save([[0.1]], force=True)

    with pytest.raises(RuntimeError, match="does not match"):
        EmbeddingCheckpoint(path, ["different"]).load()


def test_embedding_checkpoint_is_not_written_until_save_threshold(tmp_path) -> None:
    path = tmp_path / "release-embeddings.json.gz"
    checkpoint = EmbeddingCheckpoint(path, ["first"])

    checkpoint.save([[0.1]])

    assert not path.exists()
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("{}")
