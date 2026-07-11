"""CLI: build the retrieval index from processed documents.

Usage: `legal-rag-index`
"""

import sys

from legal_rag.ingestion.logging_config import configure_logging, get_logger
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.chunking import chunk_document
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.corpus import load_documents
from legal_rag.rag.store import ChromaHybridStore


def main() -> int:
    configure_logging()
    logger = get_logger(__name__)

    try:
        settings = get_rag_settings()
        documents = load_documents(settings.processed_dir, settings.dataset_manifest_path)
        if not documents:
            print(f"No processed documents found in {settings.processed_dir}", file=sys.stderr)
            return 1

        chunks = []
        for record, title in documents:
            document_chunks = chunk_document(
                record, title=title, max_chars=settings.chunk_max_chars
            )
            chunks.extend(document_chunks)
            print(f"  {title}: {len(document_chunks)} chunks ({record.page_count} pages)")

        client = AzureOpenAIClient(settings)
        print(f"Embedding {len(chunks)} chunks via Azure OpenAI ...")
        vectors = client.embed([c.embed_text for c in chunks])

        store = ChromaHybridStore(str(settings.chroma_persist_dir))
        store.index(chunks, vectors)
        logger.info(
            "index built",
            extra={"documents": len(documents), "chunks": len(chunks)},
        )
        print(f"Indexed {store.count()} chunks from {len(documents)} document(s).")
        return 0
    except Exception:
        logger.exception("index build failed")
        print("Index build failed; see logs for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
