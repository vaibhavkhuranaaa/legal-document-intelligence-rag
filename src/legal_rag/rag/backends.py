"""Construction point for the configured retrieval backend."""

from legal_rag.rag.azure_search import AzureAISearchStore
from legal_rag.rag.config import RagSettings
from legal_rag.rag.store import ChromaHybridStore, RetrievalBackend


def build_retrieval_backend(settings: RagSettings) -> RetrievalBackend:
    if settings.retrieval_backend == "azure_ai_search":
        if not settings.azure_search_endpoint or not settings.azure_search_index_name:
            raise RuntimeError("Azure AI Search was selected without its required settings")
        return AzureAISearchStore(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
        )
    return ChromaHybridStore(str(settings.chroma_persist_dir))
