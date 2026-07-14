# Architecture

This document describes the implemented architecture and its approved production
direction. Implemented components and planned components are deliberately kept
separate.

## Current implemented system

The application is a local, API-key-authenticated Streamlit and CLI demo over a
public corpus of Delaware M&A litigation. It has been validated against Azure
Document Intelligence and Azure OpenAI.

```text
Public PDF corpus
  -> Azure Document Intelligence (prebuilt-layout)
  -> Azure-SDK adapter
  -> outline parser and validation
  -> versioned DocumentRecord JSON
  -> structure-aware chunking
  -> Azure OpenAI embeddings
  -> local Chroma vector retrieval + in-process BM25, RRF fused
  -> Azure OpenAI grounded answering
  -> Streamlit UI / CLI
```

### Boundaries that are already in place

- `ingestion/adapter.py` is the Azure Document Intelligence SDK boundary.
- `ingestion/storage/base.py` defines storage independently of the local
  filesystem implementation.
- `rag/store.py` defines `RetrievalBackend` independently of the local
  Chroma/BM25 implementation.
- Construction occurs in the CLI/UI entry points; pipeline and domain logic use
  injected dependencies.

This is intentionally suitable for local development, but it is not yet a
production deployment: Chroma persists locally, authentication uses API keys,
and no Azure-hosted storage or search backend exists.

## Approved deployment direction (not yet implemented)

```text
Controlled ingestion and indexing workflow
  -> Azure Blob Storage (raw documents, processed records, manifests)
  -> Azure AI Search (production hybrid index)

Azure App Service running Streamlit
  -> managed identity
  -> Azure OpenAI + Azure AI Search + Blob Storage
  -> Application Insights
```

The public web app will serve a previously built index only. Ingestion and
indexing remain separate operations so later corpus additions do not require a
web-app redeploy. Azure AI Search and Blob Storage will be second
implementations behind the existing interfaces; the local implementations stay
available for development and deterministic tests.

## Status

- Local RAG demo: implemented and verified.
- Azure adapter layer: implemented and unit-tested. `DefaultAzureCredential`
  authentication, Blob-backed ingestion storage, and Azure AI Search hybrid
  retrieval are selected through typed settings.
- Production Azure resources, Search index schema, RBAC, observability, and
  CD: not provisioned; see [roadmap.md](./roadmap.md).
