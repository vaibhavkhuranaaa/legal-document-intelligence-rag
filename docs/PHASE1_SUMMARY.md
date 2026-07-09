# Phase 1 Summary — Document Ingestion Pipeline

Phase 1 converts a folder of public SEC EDGAR documents (PDF or common raster
image formats) into stable, structured JSON using Azure Document
Intelligence. It ends at structured JSON on disk — no LangChain, chunking,
embeddings, vector store, Azure OpenAI, retrieval, Streamlit, or deployment
is part of this phase.

## Final architecture

```
Discovery → Normalization → Azure Document Intelligence → Adapter
   → Structure Builder → Schema Mapping → Validation → Storage → Manifest
```

Orchestrated end to end by `pipeline.run_pipeline()`, invoked via the
`legal-rag-ingest` console script (`cli.py`).

## Modules

| Module | Responsibility |
|---|---|
| `models.py` | All domain models: vendor-neutral `Raw*` types, the versioned `DocumentRecord` schema, `ManifestEntry`/`RunReport` |
| `config.py` | Env-driven settings (`IngestionSettings`), loaded exactly once via `get_settings()` |
| `exceptions.py` | Typed exception hierarchy: `UserInputError`, `InfrastructureError`, `ExtractionError`, `ValidationFailedError` |
| `logging_config.py` | Structured JSON logging with `contextvars`-based context binding |
| `adapter.py` | Translates Azure's `AnalyzeResult` into the vendor-neutral `RawDocument` — the only module (besides `client.py`) permitted to import Azure SDK types |
| `storage/base.py`, `storage/local.py` | `StorageBackend` abstraction; `LocalStorageBackend` is the Phase 1 filesystem implementation |
| `discovery.py` | Enumerates source documents and classifies format by extension |
| `normalization.py` | Opens, validates (signature/emptiness), and reads each document |
| `client.py` | Azure Document Intelligence SDK wrapper: auth, submission, retry (via azure-core) |
| `structure.py` | Reconstructs section hierarchy from Azure's flat paragraph stream, using heading-text numbering heuristics |
| `mapper.py` | Assembles the final `DocumentRecord` (document ID hashing, field assembly) |
| `validation.py` | Semantic (business-rule) validation beyond Pydantic's schema validation |
| `pipeline.py` | Orchestration only: stage sequencing, exception-to-manifest translation, logging, ID bookkeeping |
| `cli.py` | Constructs and injects all infrastructure (settings, storage, client, logger) into `run_pipeline()` |

## Dependency graph

Internal imports form a strict, layered DAG (no cycles):

```
models, exceptions, logging_config, config, storage.base   (leaves)
        │
storage.local, discovery, adapter, structure, validation
        │
mapper, normalization
        │
client
        │
pipeline
        │
cli
```

Each module only imports from the layers below it. `pipeline.py` is the
first module to depend on nearly everything (by design — it's the
orchestrator); `cli.py` depends on `pipeline.py` plus the concrete
infrastructure implementations it constructs (`LocalStorageBackend`,
`AzureDocumentIntelligenceClient`).

## Key architectural decisions

Full rationale in `docs/decisions.md` (ADR-0004 through ADR-0011):

- Vendor SDK types are isolated behind `adapter.py`/`client.py`; no other module depends on Azure SDK objects.
- Storage is abstracted behind `StorageBackend` (read/write source documents, processed output, failure records, run reports) so Blob Storage can be added later without touching business logic.
- `pipeline.py` receives every dependency by injection and constructs no infrastructure itself; `cli.py` is the sole construction point.
- `schema_version` and `pipeline_version` are tracked independently.
- Failed documents are tracked by `correlation_id` (always available); `document_id` is `None` unless a real content hash was actually computed before the failure.
- Run reports are persisted through `StorageBackend.write_run_report()`, not direct filesystem access.

## Schema

`DocumentRecord` (schema_version `"1.0"`) preserves document/SEC metadata,
per-page geometry, a section hierarchy (`structure`) and a parallel flat,
citation-addressable element list (`elements`) covering paragraphs, headings,
and tables — each carrying page number, section path, and bounding regions.

## Extension points (not yet implemented)

These are seams the current design deliberately leaves open, per ADR-0005
and the Phase 1 scalability design. None of the following exists yet — this
section documents where future work would plug in, not current capability:

- **`storage/blob.py`** — a second `StorageBackend` implementation backed by
  Azure Blob Storage. `discovery.py` and `pipeline.py` would need no changes;
  only `cli.py` (or a future entry point) would construct a different
  backend.
- **Azure Functions** — `pipeline._process_document_inner()` (one document
  in, one `ManifestEntry` out) is already isolated as a single-document unit
  suitable for becoming a blob-triggered function body.
- **Azure AI Search** — a future `write_processed_document` implementation
  (or an additional storage sink) could index `DocumentRecord.elements`
  directly, since the schema was designed to be stable across this
  transition.
- **`mypy`** — deliberately deferred per ADR-0003 until the codebase has
  more surface area; not configured in Phase 1.
- **Native SEC EDGAR HTML ingestion** — approved, deferred future
  enhancement (ADR-0011). SEC EDGAR serves nearly all modern filings as
  HTML, not PDF; the pipeline currently only accepts PDF/image formats.
  Two candidate designs (HTML→PDF normalization in front of the existing
  pipeline, vs. a native HTML parser feeding `RawDocument` directly) are
  documented in ADR-0011 along with their tradeoffs. Intentionally deferred
  until Phase 1.5's PDF pipeline validation is complete, so as not to
  introduce a second ingestion format as a confounding variable mid-validation.

## Roadmap

Phase 1 (this document) is complete. Phase 1.5 (Azure Integration) is in
progress: Azure Document Intelligence and Azure OpenAI resources have been
provisioned, model deployments (`gpt-5-mini`, `text-embedding-3-small`)
verified, and connectivity confirmed against both services. The current
Phase 1.5 objective is validating the existing PDF ingestion pipeline
end-to-end against real legal documents, per `docs/roadmap.md`.

## Known limitations (heuristics, not guarantees)

- **Heading depth** is inferred from the heading text's own numbering
  convention (`"ARTICLE I"`, `"1.1"`, `"(a)"`), since Azure's layout model
  does not return heading depth.
- **Reading order** within a page is inferred from vertical bounding-region
  position, since paragraphs and tables have no shared ordering key in the
  neutral model. Accurate for single-column layouts; not for multi-column.
- **Format support** is limited to PDF and the raster image formats Azure
  Document Intelligence natively accepts (JPEG, PNG, BMP, TIFF, HEIF) — no
  HTML/DOCX/TXT conversion capability exists.
- **SEC metadata enrichment** (CIK, accession number, form type from EDGAR)
  is not implemented; `sec_metadata` is always `None` in Phase 1.

## Verification

- `uv run ruff check .` — all checks passed.
- `uv run pytest` — 109 tests passing, 0 failures, 0 warnings.
- Coverage tooling is not configured (out of Phase 1's approved tooling
  scope: Ruff and Pytest only).
- A post-implementation engineering audit was performed against the
  approved architecture (Azure SDK isolation, storage abstraction,
  dependency injection, error handling, logging, and test coverage). Four
  findings were identified and fixed: an unused exception type
  (`EmptyExtractionError`) was removed, the schema-validation failure path
  gained test coverage, `document_id` was added to the failure log line, and
  `.gitignore` was extended to cover `data/failed/` and `logs/`.
