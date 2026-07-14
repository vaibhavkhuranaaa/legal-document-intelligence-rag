# Roadmap

Work proceeds one phase at a time. Each phase must be explicitly approved before
the next begins.

## Phase 0 — Repository Bootstrap

Status: **Complete**

- Project structure, dependency management (`uv`), linting (`ruff`), and test
  harness (`pytest`) in place.

## Phase 1 — Document Ingestion Pipeline

Status: **Complete** (baseline tagged `v0.1.0-phase1`)

- Full PDF/image ingestion pipeline built and tested against Azure Document
  Intelligence's `prebuilt-layout` model: discovery, normalization, extraction,
  structure reconstruction, schema mapping, validation, storage, and manifest
  reporting. See `docs/PHASE1_SUMMARY.md` for the complete architecture summary.

## Phase 1.5 — Azure Environment & Live Validation

Status: **Complete**

- Azure resources provisioned (Document Intelligence S0, Azure OpenAI with
  `gpt-5-mini` and `text-embedding-3-small` deployments), connectivity
  verified, and the full 4-document corpus (305 pages of public Delaware
  M&A litigation) ingested end-to-end with zero failures. Section-hierarchy
  heuristic enhanced (heading-style registry with deterministic ambiguity
  warnings) and validated against live extractions.

## Phase 2 — Demo RAG Stack

Status: **Complete locally; deployment is a separate phase**

- Full retrieval-augmented answering loop, validated end-to-end against the
  real corpus with real Azure services (see ADR-0012):
  structure-aware typed chunking → Azure OpenAI embeddings → hybrid retrieval
  (Chroma + BM25, RRF-fused) behind a `RetrievalBackend` interface →
  citation-required grounded generation with an explicit refusal path →
  Streamlit UI and `legal-rag-ask` CLI.
- A full-platform architecture review (`docs/ARCHITECTURE_REVIEW.md`) defines
  the target production architecture and the remaining milestones below.

## Phase 3 — Production Deployment

Status: **In progress — deployment readiness and Azure adapter layer complete;
cloud provisioning pending**

- App Service runtime for the Streamlit demo.
- Managed Identity / `DefaultAzureCredential` in place of production API keys.
- Blob-backed storage and Azure AI Search implementations behind the existing
  `StorageBackend` and `RetrievalBackend` interfaces.
- Application Insights and an OIDC-based GitHub Actions deployment workflow.
- A separate ingestion/indexing operation so the corpus can grow without
  redeploying the public app.

Requires an Azure Pay-As-You-Go subscription before cloud resources are
provisioned.

## Future phases

Per the architecture review's priority roadmap: parser v2 (outline state
machine), Azure DI span offsets for exact reading order, and a gold-QA
evaluation harness as a CI gate. Each will be scoped in detail immediately
before implementation.

### Approved future enhancement: Native SEC EDGAR HTML Ingestion

Status: **Approved, deferred** — not yet scheduled to a specific phase number
(tentatively Phase 1.6 or a dedicated "Additional Document Sources" phase).

SEC EDGAR serves nearly all modern filings as HTML, not PDF; the current
pipeline only ingests PDF/image formats. Full rationale, and two candidate
implementation designs with their tradeoffs, are recorded in ADR-0011
(`docs/decisions.md`). This work is intentionally deferred until Phase 1.5's
PDF pipeline validation is complete and stable — introducing a second
ingestion format mid-validation would confound the results. It will be
picked up as its own dedicated milestone, not folded into Phase 1.5.
