"""Run the live gold-QA benchmark as an explicit corpus-release operation."""

from __future__ import annotations

import argparse
from pathlib import Path

from legal_rag.evaluation.models import EvaluationCheckpoint
from legal_rag.evaluation.runner import evaluate, load_gold_dataset
from legal_rag.rag.answer import AnswerService
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.backends import build_retrieval_backend
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.source_registry import SourceRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the legal RAG production release")
    parser.add_argument("--gold", type=Path, default=Path("data/evaluation/gold_qa_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/latest.json"))
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument(
        "--answer-max-completion-tokens",
        type=int,
        default=2400,
        help="release-evaluation-only completion cap; does not change production settings",
    )
    parser.add_argument(
        "--chat-request-interval-seconds",
        type=float,
        default=45.0,
        help="minimum delay between release-evaluation chat requests",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="local resumable per-question diagnostic state (defaults beside --output)",
    )
    args = parser.parse_args(argv)

    settings = get_rag_settings()
    registry = SourceRegistry.load(settings.dataset_manifest_path)
    service = AnswerService(
        AzureOpenAIClient(settings), build_retrieval_backend(settings), source_registry=registry
    )
    dataset = load_gold_dataset(args.gold)
    checkpoint_path = args.checkpoint or args.output.with_suffix(args.output.suffix + ".partial")
    initial_question_results = []
    if checkpoint_path.exists():
        checkpoint = EvaluationCheckpoint.model_validate_json(checkpoint_path.read_text())
        if (
            checkpoint.benchmark_version != dataset.benchmark_version
            or checkpoint.retrieval_k != args.k
        ):
            raise ValueError(
                "evaluation checkpoint does not match the selected benchmark or retrieval k"
            )
        initial_question_results = checkpoint.question_results

    def save_checkpoint(question_results) -> None:
        checkpoint = EvaluationCheckpoint(
            benchmark_version=dataset.benchmark_version,
            retrieval_k=args.k,
            question_results=question_results,
        )
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(checkpoint.model_dump_json(indent=2) + "\n")

    report = evaluate(
        service,
        dataset,
        k=args.k,
        answer_max_completion_tokens=args.answer_max_completion_tokens,
        chat_request_interval_seconds=args.chat_request_interval_seconds,
        initial_question_results=initial_question_results,
        on_question_complete=save_checkpoint,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n")
    print(f"Wrote {args.output} ({report.question_count} questions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
