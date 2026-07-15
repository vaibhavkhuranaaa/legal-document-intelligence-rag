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

Status: **Complete**

- App Service runtime for the original Streamlit demo, later replaced by Flask.
- Managed Identity / `DefaultAzureCredential` in place of production API keys.
- Blob-backed storage and Azure AI Search implementations behind the existing
  `StorageBackend` and `RetrievalBackend` interfaces.
- Application Insights and an OIDC-based GitHub Actions deployment workflow.
- A separate ingestion/indexing operation so the corpus can grow without
  redeploying the public app.

The production resource group, managed identity, Storage account/private Blob
container, Basic Azure AI Search service, `legal-rag-chunks` index, and its
390-chunk public corpus are provisioned. The Linux B1 App Service is running
the public Flask research workspace at the repository's live-demo URL.

## Phase 4 — Evidence-first Flask workspace

Status: **Complete — Flask/Gunicorn deployed, benchmarked, and smoke-tested**

- Flask/Gunicorn workspace with Research, Evidence, Corpus, Evaluation, and
  health routes.
- Public source registry resolving every evidence card to canonical HTTPS PDF,
  page, checksum, section, and excerpt.
- Versioned 25-question gold-QA dataset and evaluation CLI. `gold-qa-v1` ran
  against the current 390-chunk production index on 2026-07-15 and
  recorded 100% retrieval hit rate@8 and 100% citation-provenance validity.
- Source URLs, production benchmark, Flask deployment, and public smoke tests
  passed on 2026-07-15. Streamlit retirement is recorded in the follow-up
  runtime-cleanup commit.

## Phase 5A — Delaware opinion expansion

Status: **Complete — promoted and smoke-tested**

- Ten additional official Delaware court PDFs were checksum-registered and
  ingested successfully, expanding the public corpus to 14 opinions / 1,133 pages.
- The promoted Azure AI Search index contains 1,468 chunks, preserving the
  prior 390-chunk index as the rollback point.
- The 45-question `gold-qa-v2-delaware-expansion` release benchmark recorded
  100% retrieval hit rate@8 and 100% citation-provenance validity against that
  staged index. This remains a retrieval/provenance measure, not legal accuracy.

## Future phases

Per the architecture review's priority roadmap: parser v2 (outline state
machine), Azure DI span offsets for exact reading order, and corpus expansion.
The gold-QA harness is now implemented as a release check; automated Azure
execution can be added only after its release identity/credentials are scoped.

## Phase 5B — Native SEC EDGAR merger-filing ingestion

Status: **Ready for controlled publication — parser/citation gate passed**

- The native HTML parser, rate-limited explicit-URL SEC client, immutable
  SEC filing metadata, and source-kind-aware citations are implemented and
  covered by deterministic tests.
- Six official EX-2.1 merger agreements were fetched once with a declared SEC
  User-Agent solely to validate parsing. They are not registered, indexed, or
  visible in production yet.
- The sampled official filings have no stable DOM `id`/`name` fragments.
  Phase 6 now preserves a truthful visible-heading plus text-span locator and
  never appends an unresolvable fragment to an official URL.

## Phase 6 — Parser and citation accuracy

Status: **Complete — local release gates validated**

- PDF extraction retains Azure Document Intelligence character spans; native
  SEC HTML retains deterministic text offsets. Both flow through chunks,
  Azure Search payloads, citations, and the evidence UI.
- Outline reconstruction now tracks expected `ARTICLE` and decimal-heading
  successors within each parent branch and records explicit warnings on gaps.
- Semantic validation blocks incomplete/invalid spans, duplicate section IDs,
  malformed heading paths, orphaned sections, duplicate SEC heading anchors,
  and incomplete SEC provenance.
