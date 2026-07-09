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

## Phase 1.5 — Azure Environment & Live Validation (current)

Status: **In progress**

- Azure subscription discovery, resource provisioning (Document Intelligence,
  Azure OpenAI), model deployments, and connectivity verification complete.
- Current objective: validate the existing PDF ingestion pipeline end-to-end
  against real legal documents in the live Azure environment, with no new
  ingestion formats or preprocessing introduced during this validation.

## Future phases

Not yet planned in detail beyond the approved enhancement below. Each future
phase (chunking/embedding, vector store, retrieval + Azure OpenAI generation,
Streamlit UI, Azure App Service deployment) will be scoped and added here
immediately before it is implemented, along with the tradeoffs considered —
not drafted in advance.

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
