"""Run the live gold-QA benchmark as an explicit corpus-release operation."""

from __future__ import annotations

import argparse
from pathlib import Path

from legal_rag.evaluation.runner import evaluate, load_gold_dataset
from legal_rag.rag.answer import AnswerService
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.backends import build_retrieval_backend
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.source_registry import SourceRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the legal RAG release candidate")
    parser.add_argument("--gold", type=Path, default=Path("data/evaluation/gold_qa_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/latest.json"))
    parser.add_argument("--k", type=int, default=8)
    args = parser.parse_args(argv)

    settings = get_rag_settings()
    registry = SourceRegistry.load(settings.dataset_manifest_path)
    service = AnswerService(
        AzureOpenAIClient(settings), build_retrieval_backend(settings), source_registry=registry
    )
    report = evaluate(service, load_gold_dataset(args.gold), k=args.k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2) + "\n")
    print(f"Wrote {args.output} ({report.question_count} questions).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
