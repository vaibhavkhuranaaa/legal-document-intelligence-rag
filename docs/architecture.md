# Architecture

This document describes the implemented architecture and its approved production
direction. Implemented components and planned components are deliberately kept
separate.

## Current implemented system

The application is a public corpus research system over Delaware M&A litigation.
Production uses managed identity, Azure OpenAI, and Azure AI Search; local
development retains API-key/Chroma support. The live public host serves the
Flask/Gunicorn research workspace.

```text
Public PDF corpus
  -> Azure Document Intelligence (prebuilt-layout)
  -> Azure-SDK adapter
  -> outline parser and validation
  -> versioned DocumentRecord JSON
  -> structure-aware chunking
  -> Azure OpenAI embeddings
  -> Azure AI Search production retrieval / local Chroma + BM25 development retrieval
  -> Azure OpenAI grounded answering
  -> public research workspace / CLI
```

### Boundaries that are already in place

- `ingestion/adapter.py` is the Azure Document Intelligence SDK boundary.
- `ingestion/storage/base.py` defines storage independently of the local
  filesystem implementation.
- `rag/store.py` defines `RetrievalBackend` independently of the local
  Chroma/BM25 implementation.
- Construction occurs in the CLI/UI entry points; pipeline and domain logic use
  injected dependencies.

The local backend is intentionally suitable for deterministic development.
Production uses the Azure implementations behind the same interfaces; a web
request never performs ingestion, embedding, or index mutation.

### Evidence provenance and evaluation

- `data/dataset_manifest.json` is the source registry for every public opinion.
  `SourceRegistry` validates HTTPS canonical source URLs and checksum identity.
- `AnswerService` resolves each cited document ID through that registry and
  returns the canonical PDF page link, checksum, document, section, page range,
  and excerpt together.
- The Flask Evidence explorer displays that provenance without trusting model-
  composed citations.
- `data/evaluation/gold_qa_v2.json` contains the versioned 45-question gold
  benchmark across the 14-opinion public corpus. `legal-rag-evaluate` is an explicit, Azure-backed release check;
  only its recorded aggregate results may be displayed publicly.

## Production deployment direction

```text
Controlled ingestion and indexing workflow
  -> Azure Blob Storage (raw documents, processed records, manifests)
  -> Azure AI Search (production hybrid index)

Azure App Service running the public UI
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
- Production Azure resources, Search index schema, RBAC, and the promoted
  1,468-chunk expanded corpus index: provisioned and live.
- Flask/Gunicorn workspace: deployed and smoke-tested at the public host.
