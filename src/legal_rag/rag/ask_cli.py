"""CLI: ask a grounded question against the built index.

Usage: `legal-rag-ask "What did the court hold about appraisal rights?"`
"""

import sys

from legal_rag.ingestion.logging_config import configure_logging, get_logger
from legal_rag.rag.answer import AnswerService
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.store import ChromaHybridStore


def main() -> int:
    configure_logging(level="WARNING")
    logger = get_logger(__name__)

    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Usage: legal-rag-ask "your question"', file=sys.stderr)
        return 2
    question = " ".join(sys.argv[1:]).strip()

    try:
        settings = get_rag_settings()
        client = AzureOpenAIClient(settings)
        store = ChromaHybridStore(str(settings.chroma_persist_dir))
        service = AnswerService(client, store)

        answer = service.ask(question, k=settings.retrieval_top_k)

        print(answer.text)
        if answer.citations:
            print("\nSources:")
            for citation in answer.citations:
                print(f"  [{citation.marker}] {citation.display}")
        if not answer.grounded:
            print("\n(No grounded citation — treat this response with caution.)")
        return 0
    except Exception:
        logger.exception("question answering failed")
        print("Question answering failed; see logs for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
