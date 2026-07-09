# Architectural Decisions (ADR-lite)

Lightweight record of significant technical decisions and the tradeoffs behind
them. Each entry: context, decision, alternatives considered, consequences.

---

## ADR-0001: Dependency and environment management via `uv`

**Context:** Need reproducible, isolated Python environments without touching
system Python, and a single source of truth for dependencies.

**Decision:** Use `uv` for virtual environment creation and dependency
resolution/locking, driven entirely by `pyproject.toml` (+ generated `uv.lock`).
No `requirements.txt` as a primary artifact.

**Alternatives considered:** `pip` + `venv` + `requirements.txt` (slower,
no lockfile by default, more manual); `poetry` (viable, but `uv` is faster and
has become the standard for new projects).

**Consequences:** Contributors must have `uv` installed. A `requirements.txt`
can be generated on demand for deployment targets that require it
(`uv export`), but it is never hand-maintained.

---

## ADR-0002: `src` layout with package name `legal_rag`

**Context:** Need an import layout that prevents accidentally importing from
the working directory instead of the installed package, standard for
production-quality Python packages.

**Decision:** Use `src/legal_rag/` layout, installed in editable mode.

**Consequences:** Tests and tooling must run against the installed package
(via `uv run`), not via ad hoc `PYTHONPATH` manipulation.

---

## ADR-0003: Defer `mypy` until the codebase has enough surface area

**Context:** Static typing is valuable but adds friction disproportionate to a
near-empty codebase.

**Decision:** Configure only `ruff` (lint) and `pytest` (tests) in Phase 0.
Introduce `mypy` in a later phase once there are real modules and interfaces
worth type-checking.

**Consequences:** Type errors will not be caught until `mypy` is introduced;
acceptable given the current scope.

---

## ADR-0004: Isolate the Azure SDK behind an adapter layer

**Context:** Phase 1 (document ingestion) calls Azure Document Intelligence
and receives SDK-defined response objects (`AnalyzeResult` and its nested
types). If those types are passed directly into structure-building, schema
mapping, and validation logic, the entire business logic layer becomes
coupled to a third-party SDK's object model.

**Decision:** Vendor SDKs are isolated behind adapters. Business logic must
not depend directly on Azure SDK types. A dedicated adapter module is the only
place in the codebase allowed to import `azure.ai.documentintelligence`
response types; it translates them into internal, neutral models immediately
after the API call returns. Every downstream stage (structure building,
schema mapping, validation, persistence) operates only on these internal
models.

**Alternatives considered:** Passing `AnalyzeResult` directly into structure
and mapping logic — rejected because it would make unit tests depend on
constructing or mocking Azure SDK objects, and would couple core business
logic to Azure's API surface, making it harder to test, harder to reason
about, and harder to change providers or SDK versions later.

**Consequences:** One additional translation module to maintain, and it must
be updated if Azure changes its response shape — but that cost is isolated to
a single, narrow module instead of spread across the codebase. Business logic
becomes independently unit-testable with plain fixtures, with no SDK
dependency at import time.

---

## ADR-0005: Storage abstraction (`storage/base.py` + `storage/local.py`) instead of a filesystem-coupled writer

**Context:** The original design's `writer.py` wrote processed/failed output
directly via `pathlib`. The Phase 1 design already commits to evolving from
local disk to Azure Blob Storage (and later Azure Functions) without changing
business logic, but a writer coupled directly to the filesystem would need to
be rewritten, not extended, when that migration happens.

**Decision:** Replace `writer.py` with a `storage/` package: `storage/base.py`
defines a storage interface (list/read source documents, write processed
output, write failure records); `storage/local.py` is the filesystem
implementation used in this phase. `discovery.py` and the persistence stage of
`pipeline.py` depend only on this interface, injected as configuration, never
on `pathlib` directly.

**Alternatives considered:** Keep `writer.py` as direct filesystem I/O and
defer the abstraction until the Blob Storage phase actually arrives —
rejected because retrofitting an interface after callers already depend on
concrete file paths is riskier and more invasive than designing the interface
now, while it costs almost nothing to do so.

**Consequences:** A small amount of upfront indirection (one interface, one
implementation) in exchange for `storage/blob.py` being addable later as a
second implementation, with zero changes to `pipeline.py`'s orchestration or
any business logic.

---

## ADR-0006: Extended processing manifest for per-document auditability

**Context:** A minimal run-level success/failure summary is not enough to
audit or debug a batch run without opening individual output files, and won't
scale to the observability needs of a future Azure Functions deployment,
where each invocation processes one document and needs to be traceable
independently.

**Decision:** Each run produces a manifest with one entry per document,
capturing: `document_id`, `run_id`, `correlation_id`, processing duration,
page count, output path, warnings, and extraction status. `run_id` identifies
the batch invocation; `correlation_id` identifies a single document's
processing attempt within that run (also used in structured logs, per the
Phase 1 error-handling design); `document_id` is the document's own stable,
content-addressed identity from the schema.

**Consequences:** Slightly more structured data to produce per document, but
a batch run becomes fully auditable from the manifest alone — which document
succeeded or failed, how long it took, how many pages, and where its output
went — without reopening every JSON file or grepping logs.

---

## ADR-0007: `pipeline_version` tracked independently from `schema_version`

**Context:** The document JSON schema (`schema_version`) and the ingestion
codebase that produces it (`pipeline_version`) change for different reasons
and at different rates. Coupling them would force a schema version bump every
time the pipeline's internal logic changes, even when the output JSON shape
is unaffected — or conversely, hide a real code change behind an unchanged
version number.

**Decision:** `schema_version` governs the JSON output contract that
downstream phases (chunking, embeddings, retrieval) depend on, and only
changes on a breaking structural change. `pipeline_version` tracks the
ingestion codebase's own version and is recorded both in each document's
`extraction` metadata and in the run manifest (ADR-0006), independent of
`schema_version`.

**Consequences:** Two version numbers to maintain instead of one, but each
answers a different operational question: "is this JSON shape compatible
with what I expect?" (`schema_version`) versus "which build of the pipeline
produced this, for reproducibility and debugging?" (`pipeline_version`).

---

## ADR-0008: Configuration is loaded exactly once, behind a single accessor

**Context:** Environment-variable access scattered across modules (`os.environ`
or `os.getenv` called wherever a value is needed) makes configuration
implicit, hard to trace, and hard to test — every module that reads the
environment directly becomes coupled to process environment state instead of
an explicit dependency.

**Decision:** All configuration is parsed once, by `config.IngestionSettings`,
accessed exclusively through `config.get_settings()` (an `lru_cache`-backed
singleton). Application code must never call `os.environ` / `os.getenv`
directly — every module that needs configuration receives it via
`get_settings()` or as an injected parameter, never by reading the
environment itself.

**Consequences:** Configuration has one authoritative source and one place
where env-var names are defined. Tests that need different configuration call
`get_settings.cache_clear()` after patching the environment, rather than
monkeypatching scattered `os.getenv` calls throughout the codebase.

---

## ADR-0009: Run reports are persisted through `StorageBackend`, not the filesystem directly

**Context:** `pipeline.py`'s orchestrator produces a `RunReport` summarizing
every document processed in a run. The original Phase 1 directory design
placed run reports under `logs/`, which raised the question of whether
`pipeline.py` should write them directly via `pathlib`, bypassing the storage
abstraction built for ADR-0005.

**Decision:** `StorageBackend` gains a fourth method, `write_run_report(run_id,
content) -> str`, alongside the three document-I/O methods. `pipeline.py`
calls this instead of touching the filesystem itself, keeping it fully
independent of the persistence mechanism — consistent with ADR-0005's goal
of `pipeline.py` never depending on `pathlib` or any concrete storage
implementation.

**Alternatives considered:** Writing the `RunReport` directly to
`settings.logs_dir` from `pipeline.py` — rejected because it would
reintroduce exactly the filesystem coupling ADR-0005 removed, just for a
different artifact, and would need separate handling again when Blob
Storage or Azure Functions are introduced.

**Consequences:** `LocalStorageBackend` takes a fourth constructor parameter,
`reports_dir`. A future `storage/blob.py` implementation must also implement
`write_run_report`, alongside the other three methods.

---

## ADR-0010: No path-derived document ID fallback on early failures

**Context:** A document can fail before `mapper.compute_document_id()` ever
runs (e.g. `UnsupportedFormatError`, raised before any bytes are read). The
`ManifestEntry` and failure record still need a stable identifier to file
the failure under.

**Decision:** `ManifestEntry.document_id` is `str | None` — `None` when no
content-derived ID could be computed, never a fallback hash derived from the
file path or ref. Every document already gets a `correlation_id` (generated
before any processing begins) that uniquely identifies its processing
attempt within a run; this is the identifier `write_failure_record` files
under and the field a human or downstream tool uses to track a failed
document. If a real `document_id` *was* computed before the failure occurred
(e.g. a document that fails semantic validation, which happens after
`document_id` is known), it is preserved in the exception's `context` and
still populates `ManifestEntry.document_id`.

**Alternatives considered:** Hashing the file path/ref as a fallback
pseudo-document-ID — rejected because it would silently conflate a real,
content-addressed identity with a manufactured one that looks identical in
the schema, misleading anyone reading the manifest into thinking a stable
content hash exists when it doesn't.

**Consequences:** Consumers of `ManifestEntry` must handle `document_id`
being `None` and use `correlation_id` as the always-present tracking key for
failed documents.

---

## ADR-0011: Native SEC EDGAR HTML ingestion is an approved, deferred future enhancement

**Context:** While selecting real documents for Phase 1.5 validation, direct
inspection of SEC EDGAR confirmed that essentially all modern filings —
merger agreements, asset purchase agreements, proxy statements — are served
as `.htm`, not `.pdf`. Native PDF exhibits are effectively extinct on EDGAR
for these document types (this has been true since EDGAR's shift to
structured HTML filings in the early 2000s). The pipeline's `normalization.py`
only accepts PDF and raster image formats by design (see its module
docstring: "no format conversion happens here"), so real EDGAR filings
currently require an out-of-pipeline HTML→PDF conversion step before they
can be ingested at all.

**Why this matters strategically:** the project's stated corpus source
(`docs/product.md`) is SEC EDGAR. Long-term, requiring every document to be
manually converted before ingestion is a real limitation on the platform's
usability and on how directly it can be pointed at a live EDGAR corpus
(e.g., an automated download-and-ingest pipeline). Native HTML support would
also, in principle, preserve *more* structural signal than a PDF
intermediary — HTML carries semantic tags (`<h1>`, `<table>`, list nesting)
that a PDF rendering flattens into position-only layout, which is exactly
the information `structure.py`'s heading-depth heuristics currently have to
*reconstruct* from Azure's flat paragraph stream.

**Decision:** Do not implement HTML ingestion now. Phase 1.5's sole
objective is validating the existing PDF pipeline against real documents;
introducing a second ingestion format during that validation would add a
second variable to every result, making it unclear whether a problem is in
the core pipeline or in new format-handling code. This is recorded as an
**approved future enhancement**, not a rejected idea, to be scoped as its
own dedicated milestone (tentatively Phase 1.6 / "Additional Document
Sources") only after the PDF pipeline has a verified, stable production
baseline. See `docs/roadmap.md` and `docs/PHASE1_SUMMARY.md`'s "Extension
points" section for the forward pointers.

**Two implementation options considered for that future milestone:**

**Option A — HTML → HTML Normalization → PDF → existing pipeline**
```
HTML → HTML Normalization → PDF → Azure Document Intelligence (unchanged)
```
- *Implementation complexity:* Low. Adds one new normalization step (an
  HTML→PDF renderer, e.g. a headless-browser-based converter) ahead of the
  existing, unmodified pipeline. `adapter.py`, `structure.py`, `mapper.py`,
  `validation.py` need no changes at all.
- *Maintainability:* High — the large majority of the pipeline (everything
  from Azure onward) is completely untouched, so this option carries almost
  no ongoing maintenance burden beyond the converter itself.
- *OCR accuracy:* Good — converting clean, machine-generated HTML to PDF
  produces crisp, digitally-rendered text, which Azure Document Intelligence
  reads at least as well as it reads today's manually-converted PDFs (this
  is, in fact, exactly what was done manually for Phase 1.5's documents).
- *Metadata preservation:* Limited to whatever survives the PDF rendering —
  HTML's semantic structure (`<h1>`, `<table>`, nested lists) is flattened
  into visual layout, so `structure.py` still has to *reconstruct* hierarchy
  from position and heading-text heuristics, exactly as it does today. No
  improvement over the current approach on this axis.
- *Processing cost:* One extra conversion step per document (cheap, local,
  no additional Azure spend) plus the unchanged Azure Document Intelligence
  cost per page.
- *Long-term scalability:* Good — this option is a thin adapter in front of
  an already-proven pipeline, so it scales exactly as well as the existing
  pipeline does.

**Option B (preferred long-term vision) — HTML → Native HTML Parser →
Internal Document Model → existing downstream pipeline**
```
HTML → Native HTML Parser → RawDocument (bypassing Azure) → structure.py → mapper.py → validation.py → storage
```
- *Implementation complexity:* Higher. Requires a new parser translating
  HTML's DOM (headings, tables, paragraph roles) directly into the existing
  `RawDocument`/`RawParagraph`/`RawTable` neutral models from `models.py` —
  effectively a second "adapter," parallel to `adapter.py`, but for HTML
  instead of Azure's `AnalyzeResult`. `structure.py` onward would be reused
  unchanged, since they already operate on `RawDocument`.
- *Maintainability:* A second parsing path to maintain long-term (HTML
  structure varies more across filers/years than Azure's normalized output
  does), but it inherits the same domain models and downstream stages, so it
  doesn't fragment the schema or duplicate business logic.
- *OCR accuracy:* Not applicable — no OCR occurs at all for these documents,
  since the source text is already digital. This is a genuine accuracy
  *ceiling improvement* over Option A: zero OCR-introduced error is possible
  for HTML-sourced filings, versus Option A's (small but nonzero) OCR risk
  from the PDF intermediary.
- *Metadata preservation:* Best possible — HTML's actual semantic tags
  (`<h1>`–`<h6>`, `<table>`, list nesting, `id`/anchor attributes for
  cross-references) can be mapped directly to `RawParagraphRole`/hierarchy
  depth, rather than inferred from heading-text numbering patterns the way
  `structure.py` does today. This directly reduces reliance on the
  documented heuristic limitations in `docs/PHASE1_SUMMARY.md`.
- *Processing cost:* Lower than Option A for these documents — no Azure
  Document Intelligence API call needed at all (zero per-page Azure cost),
  since the parser reads structured HTML directly.
- *Long-term scalability:* Best, but only after the upfront parser
  investment — HTML parsing is significantly cheaper and faster than an
  Azure API round-trip, so this option scales better to a large, automated
  EDGAR-wide corpus. The risk is parser fragility across EDGAR's real-world
  HTML variability (different filing agents produce different markup
  conventions across decades of filings).

**Consequences:** No code changes now. When this milestone is picked up,
Option B is the preferred long-term target given its metadata and cost
advantages, but Option A remains a reasonable, low-risk fallback if EDGAR's
HTML variability makes a robust native parser impractical within scope.
