# Architecture Review — Legal Document Intelligence Platform

**Reviewer role:** Principal AI Architect / CTO-level review
**Date:** 2026-07-11
**Scope:** Entire platform lifecycle, ingestion through deployment. No code was changed as part of this review.
**Grounding:** Every claim below is based on direct inspection of this repository (14 ingestion modules, 115 tests, ADR-0001–0011, live Azure validation runs `20260709T095655Z` and `20260711T203821Z`), not on assumptions.

---

## 1. Executive Summary

The project has an unusually strong foundation for its stage: strict vendor-SDK isolation, storage abstraction, dependency injection, typed errors, structured logging, versioned schema, and disciplined ADR practice. The ingestion pipeline is validated end-to-end against real Azure services with a real document. This foundation should be preserved essentially as-is.

The review finds three architecture-level problems that must be resolved before the RAG layers are built, and one strategic misalignment that must be resolved by a product decision:

1. **Product/corpus drift (strategic).** `docs/product.md` defines an *M&A / SEC EDGAR* platform, but the validated corpus is *Delaware Chancery court opinions* — a workaround for EDGAR serving HTML (ADR-0011 deferred HTML ingestion). The platform is currently validating on documents the product spec says are out of scope, and cannot ingest the documents the product spec says are in scope. Either HTML ingestion moves up the roadmap, or the product spec must be updated to include judicial opinions. This is a decision, not a defect — but leaving it unresolved will contaminate every downstream design choice (chunking, metadata, evaluation questions).

2. **The parser reasons about heading *styles*, not outline *state*.** Confirmed empirically: the recent enhancement fixed the staircase defect, but two deterministic failure modes remain (decimal absolute-reset; cross-branch style-name collision). The correct target is an outline state machine that tracks expected successors per open branch. This is the single highest-leverage pre-RAG investment, because `section_path` is the citation backbone of the entire product.

3. **Reading order is inferred when it could be exact.** The adapter discards Azure DI's `spans` (character offsets into the full `content` string). The y-coordinate sort heuristic in `structure.py` exists *only because* that information was dropped. Carrying span offsets through the adapter eliminates a documented limitation outright and gives every element an exact anchor into source text — valuable for citation highlighting later.

4. **A silent telemetry gap (small, but real).** The new `DocumentStructure.warnings` field is not wired into `ExtractionInfo.warnings` — parser ambiguity warnings currently die inside `pipeline.py` unpersisted. The observability design is right; one connection is missing.

Everything else — RAG design, chunking, retrieval, deployment — does not exist yet, and the review's job there is to specify what to build. The recommendation is deliberately unfashionable: **structure-aware parent-child retrieval over hybrid (BM25 + vector) search with metadata filtering**, using the section hierarchy the pipeline already produces. No GraphRAG, no agentic retrieval, no late interaction. The corpus is small, the documents are deeply structured, and the schema already contains exactly the hierarchy that parent-child retrieval needs — the expensive part of hierarchical RAG is already built.

---

## 2. Architecture Score: **7.5 / 10**

| Dimension | Score | Note |
|---|---|---|
| Code architecture & boundaries | 9 | Adapter isolation, DI, storage abstraction are textbook |
| Schema design | 8 | Dual tree/flat representation is exactly right for RAG; spans missing |
| Testing | 7 | 115 tests, good coverage of logic; one broken test (env leakage), no coverage metric, no mypy |
| Observability | 7 | Structured logging + manifests strong; one unwired warnings path |
| Parser correctness | 6 | Improved, but two known deterministic failure modes on real documents |
| Product alignment | 5 | Corpus no longer matches product spec |
| Production/deployment posture | 4 | Free Trial subscription + spending limit; keys in `.env`; nothing deployed |
| RAG layers | n/a | Not yet built (correctly so — phased) |

Not scored higher because a platform is judged on its weakest strategic link (product alignment, subscription), not its strongest module.

---

## 3. Critical Issues

**C1 — Product/corpus misalignment (strategic, blocking for evaluation design).**
The product spec (`product.md`) promises M&A transaction-document intelligence over SEC EDGAR filings (8-K, S-4, merger agreements). The validated corpus is court opinions from Delaware Chancery. These have different structure (judicial outline vs. ARTICLE/Section contract structure), different user questions ("what did the court hold" vs. "what are the termination rights"), and different chunking needs (no defined-terms article, no reps & warranties). Every downstream layer — chunk types, metadata schema, gold evaluation questions — depends on which corpus is the real target. **Decision required before Phase 2.** Options: (a) pull ADR-0011's HTML ingestion forward and realign to EDGAR agreements; (b) broaden the product spec to "M&A transaction documents and related litigation"; (c) manually convert a small set of EDGAR agreements to PDF as a stopgap corpus (out-of-pipeline conversion, consistent with the discipline used to date). Recommendation: **(b) + (c)** now, (a) as the already-approved future milestone.

**C2 — Free Trial subscription with spending limit (blocking for deployment).**
`spendingLimit: On`, trial-grade quota. App Service + Azure AI Search Basic (~$75/mo) + OpenAI usage will exceed the trial ceiling or be blocked mid-operation when credit exhausts. The deployment milestone requires a Pay-As-You-Go upgrade. This should be scheduled deliberately, not discovered as a failure during deployment week.

**C3 — Parser: style-based rather than outline-state-based (known, now precisely characterized).**
Two residual deterministic failure modes on the live Abraham document: (i) bare numbered items (`"1."`) reset to depth 1 because `decimal` is an absolute style; (ii) letter lists under different parents merge because matching is keyed by style *name* with no branch scoping. Both are consequences of not modeling outline state. See §8 for the recommended architecture.

**C4 — Structure warnings not persisted.**
`DocumentStructure.warnings` exists and is tested, but `pipeline.py` does not pass it into `ExtractionInfo.warnings` or the manifest. Ambiguity events are currently invisible in output artifacts. One small, in-scope wiring change (pipeline-level), plus a test.

**C5 — Test isolation defect.**
`test_main_returns_one_when_settings_are_invalid` fails because the real `.env` on disk overrides `monkeypatch.delenv` (pydantic-settings re-reads the file). Pre-existing, confirmed unrelated to recent changes. It means CI will fail for any contributor with a local `.env`, and the test currently performs a *real Azure ingestion run* as collateral damage — a test that costs money. Fix by forcing `_env_file=None` in CLI tests or isolating cwd.

**C6 — Dual manifest provenance gap.**
`data/dataset_manifest.json` (curated corpus registry) and the pipeline's run manifests are unconnected — nothing links a `DocumentRecord` back to the dataset entry (title, court, case name) that a RAG citation UI will need to display. The dataset manifest is also not yet committed. `SecMetadata` is EDGAR-shaped and always `null`; the actual corpus needs case-law-shaped metadata. This is a schema-extension decision to make consciously in Phase 2, not by accident.

---

## 4. Recommended Changes (ranked)

| # | Change | Effort | When |
|---|---|---|---|
| 1 | Resolve C1 (product decision + update product.md) | Decision + docs | Immediately |
| 2 | Wire `DocumentStructure.warnings` → `ExtractionInfo.warnings` + manifest (C4) | Hours | Immediately (pipeline hardening) |
| 3 | Fix CLI test isolation (C5) | Hours | Immediately |
| 4 | Parser v2: outline state machine (§8) | Days | Before chunking |
| 5 | Carry DI `spans` through adapter; replace y-sort reading order | 1–2 days | With parser v2 (same schema-extension window) |
| 6 | Extend source metadata for case-law documents; link dataset manifest → DocumentRecord | 1 day | Phase 2 start |
| 7 | Ingest remaining 3 corpus documents; validate parser v2 against all 4 | Hours + ~$3 Azure | After parser v2 |
| 8 | Subscription upgrade to Pay-As-You-Go (C2) | Admin task | Before deployment milestone |
| 9 | Introduce `pytest-cov` + `mypy` (ADR-0003 trigger point reached: 14 modules, interfaces stable) | 1 day | Phase 2 |
| 10 | Discovery: skip dotfiles (`.gitkeep` failure records are per-run noise) | Minutes | Opportunistic |

---

## 5. Recommended Final Architecture

```
                        ┌────────────────────────────────────────────┐
                        │                INGESTION (exists)           │
 PDF (native)  ───────► │ discovery → normalization → DI client →     │
 HTML (ADR-0011, later) │ adapter(+spans) → outline parser v2 →       │
                        │ mapper → validation → storage → manifest    │
                        └───────────────┬────────────────────────────┘
                                        │ DocumentRecord v1.x (extended, not broken)
                        ┌───────────────▼────────────────────────────┐
                        │            ENRICHMENT (new, Phase 2)        │
                        │ section-aware chunker → chunk records       │
                        │ (child chunks + parent sections, typed:     │
                        │  clause / definition / table / recital)     │
                        └───────────────┬────────────────────────────┘
                                        │ ChunkRecord (new schema, references element_ids)
                        ┌───────────────▼────────────────────────────┐
                        │            INDEXING (new, Phase 3)          │
                        │ embeddings (text-embedding-3-small)         │
                        │ RetrievalBackend interface:                 │
                        │   dev: Chroma (vector) + BM25 (lexical)     │
                        │   prod: Azure AI Search (hybrid + semantic  │
                        │         ranker) — one interface, two impls  │
                        └───────────────┬────────────────────────────┘
                        ┌───────────────▼────────────────────────────┐
                        │            ANSWERING (new, Phase 4)         │
                        │ query → hybrid retrieve (children) →        │
                        │ metadata filter → rerank → expand to        │
                        │ parents → grounded generation (gpt-5-mini)  │
                        │ → citations (section_path + page + doc)     │
                        │ → refusal path when evidence insufficient   │
                        └───────────────┬────────────────────────────┘
                        ┌───────────────▼────────────────────────────┐
                        │      EVALUATION (new, Phase 4, gate)        │
                        │ gold QA set; retrieval hit-rate, citation   │
                        │ accuracy, faithfulness; run in CI on fixtures│
                        └───────────────┬────────────────────────────┘
                        ┌───────────────▼────────────────────────────┐
                        │      UI + DEPLOYMENT (Phases 5–6)           │
                        │ Streamlit on App Service; Managed Identity; │
                        │ Blob Storage; AI Search; App Insights       │
                        └────────────────────────────────────────────┘
```

The architectural pattern that already works here — pure logic behind injected interfaces, one construction point, versioned schemas — is simply repeated for each new layer: `Chunker`, `EmbeddingClient`, `RetrievalBackend`, `AnswerService`.

---

## 6. Recommended RAG Architecture

Evaluation of each candidate (Azure compat = fits AI Search + Azure OpenAI without exotic infra):

| Approach | Benefit | Drawback | Complexity | Azure fit | Cost | Legal fit | M&A fit | Prod fit | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| Naive RAG (flat chunks) | Simple | Loses hierarchy the pipeline already built; citations weak | Low | ✅ | $ | Poor | Poor | OK | Reject — wastes existing structure |
| **Hierarchical / Parent-Child** | Precise matching on small chunks, coherent context from parents; citations map to sections | Slightly more index bookkeeping | Med | ✅ | $ | **Excellent** | **Excellent** | ✅ | **Adopt — core pattern** |
| Recursive retrieval | Multi-hop | Mostly subsumed by parent-child here | Med | ✅ | $$ | Good | Good | OK | Defer |
| Multi-vector (e.g. section summaries) | Better recall on abstract queries | Extra generation cost per section | Med | ✅ | $$ | Good | Good | OK | Optional later add-on |
| Late interaction (ColBERT-style) | Strong relevance | Not supported by AI Search; self-hosted infra | High | ❌ | $$$ | Good | Good | Poor here | Reject |
| Contextual compression | Fits more evidence in context | Latency + cost per query; risk of compressing away legal nuance | Med | ✅ | $$ | Risky | Risky | OK | Defer — legal text resists lossy compression |
| **Hybrid search (BM25 + vector)** | Legal queries are exact-term-heavy (§ numbers, defined terms, party names) — lexical is essential | None material | Low | ✅ native | $ | **Essential** | **Essential** | ✅ | **Adopt** |
| Knowledge graph augmentation | Cross-document entity reasoning | Build/maintain a graph for a 4-doc corpus | High | Partial | $$$ | Overkill | Future value | Poor now | Defer |
| **Metadata-aware retrieval** | Filter by doc, court, year, section type, chunk type | Requires the metadata work in C6 | Low | ✅ native | $ | **Essential** | **Essential** | ✅ | **Adopt** |
| Agentic retrieval | Handles complex multi-step questions | Latency, nondeterminism, hard to evaluate, hard to demo reliably | High | ✅ | $$$ | Premature | Premature | Poor now | Defer |
| Self-RAG | Self-critique reduces hallucination | Doubles+ LLM cost/latency; simpler grounding rules get 90% of value | High | ✅ | $$$ | Premature | Premature | Poor now | Defer — use citation-required + refusal instead |
| GraphRAG | Corpus-wide thematic synthesis | Expensive index build; wrong tool for clause lookup | High | Partial | $$$$ | Wrong shape | Wrong shape | Poor | Reject for this product |

**Recommendation: Parent-Child retrieval + Hybrid search + metadata filtering, with the built-in Azure AI Search semantic reranker in production.** Rationale: the product's core promise is *citation-backed clause/holding lookup*, which is precision retrieval over deeply structured documents — exactly what this stack does best. The pipeline's `structure`/`elements`/`section_path` output means the hard part of hierarchical RAG (having a hierarchy) is already done. Everything deferred above can be layered on later without re-architecture because retrieval sits behind an interface.

---

## 7. Recommended Retrieval Strategy

- **Vector store, dev:** Chroma (already planned, zero cost, local). **Prod:** Azure AI Search — hybrid (BM25 + HNSW vector) + semantic ranker in one managed service. Both behind a single `RetrievalBackend` interface (mirror of the `StorageBackend` pattern, ADR-0005 style).
- **BM25:** non-negotiable for legal text. Statute cites ("§ 18-209(i)"), defined terms ("Material Adverse Effect"), party names, and docket numbers are exact-match queries that pure vector search handles badly. In dev, pair Chroma with a lightweight BM25 (e.g. `rank_bm25`) and fuse with reciprocal rank fusion so dev/prod behavior stays comparable.
- **Reranking:** use AI Search's built-in semantic ranker (L2) in production rather than deploying a separate cross-encoder service — one less component, no extra hosting, adequate for this corpus size. Revisit only if evaluation shows a relevance ceiling.
- **Filtering:** metadata filters on `document_id`, court/case fields, `chunk_type`, page range. "Search only within this agreement" is a core legal-UX requirement.
- **Context assembly:** retrieve child chunks (k≈8–12) → dedupe → expand to parent sections (capped) → assemble with per-chunk citation headers.
- **Citation preservation:** every chunk carries `document_id`, `section_path`, `page_number`(s), and source `element_ids`. Generation is instructed to cite chunk IDs; the app resolves IDs to human citations ("Abraham v. Estate of Wirtz, §II.A.2, p. 15"). Never let the model compose citations from memory.
- **Compression:** none in v1 (see table). Token budgets are managed by chunk sizing and parent caps instead.

---

## 8. Recommended Parser Architecture

**Verdict: Hybrid — keep the heading-style registry as the lexical layer; add an outline state machine as the resolution layer. Do not build a grammar parser.**

| Option | Assessment |
|---|---|
| Heading heuristic (original) | Superseded; staircase defect proven on live data |
| Heading style parser (current) | Right lexical layer, wrong resolution model — style-name matching without branch state produces C3's failure modes |
| **Outline state machine** | **Correct model.** Legal outlines are enumerable sequences. Track, per open branch, the enumerator kind *and its current value*; predict expected successors ("after II.A.1 the legal next tokens are: 2 (sibling), B (parent-sibling), III (grandparent-sibling), or a new child level"). Resolution = match the observed enumerator against predicted successors, most-nested first. |
| Grammar parser | Overkill: legal headings are not a context-free language across filers/courts; a grammar would be perpetually chasing exceptions |
| Tree parser | A tree is the *output*, not a parsing strategy |
| Pure ML/LLM structuring | Nondeterministic, unauditable, per-document cost; wrong fit for a component whose whole value is deterministic citations |

Why the state machine specifically fixes the two live failure modes: (i) `"1."` after `II.A` is predicted as *child of A* (new numbered branch) or sibling of an open numbered branch — never an absolute depth-1 reset, because bare enumerators are always resolved against state; (ii) `"A."` under `II` cannot merge into the closed letter branch under `I`, because that branch's state was popped when `II` opened — successor matching is inherently branch-scoped. Sequence prediction also resolves the single-character Roman/letter ambiguity naturally: after `B.` the successor `C.` is a letter; after `II.` the successor `III.` is Roman.

Keep: the style registry (as tokenizer for enumerator kinds), `DocumentStructure` including `warnings`, all existing tests (extend, don't rewrite), the pure-function design. Dotted decimals (`2.3`) remain absolute — they genuinely are self-describing. Migration difficulty: **moderate** (one module + tests, no schema change). Priority: **before chunking** — chunk quality is bounded by `section_path` quality. Testing: keep all current tests; add per-fixture golden trees for all 4 corpus documents once ingested; property tests for successor prediction. Deployment impact: none (pure logic).

---

## 9. Recommended Chunking Strategy

**Structure-aware, typed, parent-child chunks. No fixed-size chunking except as an overflow cap.**

- **Unit of retrieval (child chunk):** contiguous paragraph runs within a leaf section, target ~250–500 tokens, split at paragraph boundaries (never mid-sentence), with a hard token cap for pathological paragraphs.
- **Unit of context (parent):** the enclosing section (full text or capped), addressed by `section_id`.
- **Typed chunks:** `clause` (default), `definition` (detectable pattern: `"Term" means …` — one chunk per defined term, critical for M&A agreements), `table` (atomic, never split, serialized with headers), `recital` (WHEREAS blocks), `heading-context` (path prefix prepended to every chunk's embed-text so "the Company shall…" embeds with its section identity).
- **Cross-references** ("as defined in Section 1.1"): store detected references as chunk metadata now; resolve at answer-assembly time later. Do not build a resolver in v1.
- **Page boundaries:** never chunk on them; they are layout, not semantics. Retain page numbers as citation metadata (already in the schema).
- **Footnotes:** merge bare-marker fragments (observed live: `para-93` = `"14"`) into adjacent footnote text or drop markers; footnote *text* attaches to its section as low-priority content.
- **Prepend path context:** each chunk's embedded text = `[Case/Doc name › section_path]` + text. Cheap, materially improves retrieval on ambiguous pronouns and generic clause language.
- Chunk records are a **new schema** (`ChunkRecord`, own version), referencing `DocumentRecord` by `document_id`/`element_ids` — the ingestion schema stays untouched.

---

## 10. Azure Architecture

| Concern | Recommendation |
|---|---|
| Region | East US (already provisioned; correct) |
| Document Intelligence | `di-legal-rag-dev` S0 (done) |
| Azure OpenAI | `oai-legal-rag-dev` S0; `gpt-5-mini` (GlobalStandard 10K TPM — raise if RAG latency demands), `text-embedding-3-small` |
| Vector/search | Azure AI Search **Basic** (~$75/mo) at deployment milestone only; free tier lacks semantic ranker — acceptable to start free and upgrade when reranking is evaluated |
| Storage | One Storage Account (`stlegalragdev`), Standard_LRS: raw/processed/failed/reports containers via the existing `StorageBackend` seam (`storage/blob.py`) |
| Identity | Migrate `.env` keys → `DefaultAzureCredential` + user-assigned Managed Identity at deployment (already agreed); then `--disable-local-auth true` on both Cognitive Services resources |
| Key Vault | Only if any non-Entra secret remains post-migration; likely unnecessary — prefer eliminating secrets over vaulting them |
| Monitoring | Log Analytics workspace + Application Insights; attach a handler to the `legal_rag` logger (the design explicitly reserved this seam) |
| **Subscription** | **Upgrade to Pay-As-You-Go before the deployment milestone (C2)** |

## 11. Deployment Architecture

- **Compute:** Azure App Service (Linux, B1) running Streamlit — matches product spec; adequate for portfolio traffic. Container Apps is a fine alternative but adds registry + provider setup for no benefit at this scale.
- **CI/CD:** extend the existing GitHub Actions workflow with a deploy job (OIDC federation to Azure — no publish-profile secrets), gated on tests + lint, deploying on tag.
- **Config:** App Service app settings replace `.env`; `AZURE_CLIENT_ID` for the user-assigned identity; same `IngestionSettings` mechanism, zero code churn (ADR-0008 pays off here).
- **Cost posture (monthly, prod-lite):** App Service B1 ~$13, AI Search Basic ~$75, Storage <$1, OpenAI usage-based (portfolio load: <$5), App Insights <$5. ≈ **$100/mo** — fine on PAYG, impossible on the Free Trial. Cost-optimization option: AI Search Free tier + no semantic ranker ≈ **$20/mo** total for demo periods.
- **Scaling:** none needed; document the path (App Service plan scale-up; AI Search replicas) rather than building it.

## 12. Technical Debt (full register)

| Item | Severity | Source |
|---|---|---|
| Parser outline-state limitations (C3) | High | Live validation |
| Product/corpus drift (C1) | High | Review finding |
| Structure warnings unpersisted (C4) | Medium | Review finding |
| CLI test env leakage; test performs real Azure call (C5) | Medium | Pre-existing |
| Adapter drops DI `spans`; y-sort reading order | Medium | Design choice, now revisitable |
| `SecMetadata` EDGAR-shaped, always null; no dataset-manifest linkage (C6) | Medium | Phase-2 blocker |
| No mypy, no coverage metric | Low-Med | Deferred by ADR-0003; trigger point reached |
| `.gitkeep` failure-record noise per run | Low | Design consequence |
| Heading/footnote concatenation ("BACKGROUND1"), bare footnote markers | Low | Azure output; handle at chunking |
| `pipeline_version` = package version (0.1.0, never bumped) | Low | Process |
| Dataset manifest uncommitted | Low | Pending decision |

## 13. Things That Should NOT Be Changed

- Adapter isolation of Azure SDK types (ADR-0004) — extend the adapter (spans), never bypass it.
- `StorageBackend` abstraction and DI-everywhere; `cli.py` as sole construction point.
- The `DocumentRecord` dual tree/flat schema — it is *the* enabler of the recommended RAG design. Extend additively (spans, case metadata) under the existing `schema_version` discipline.
- Typed exception taxonomy; per-document failure isolation; correlation-ID manifests.
- Structured logging design (`bind_context`) — it was built for the App Insights future and needs no rework.
- `uv`/`ruff`/`pytest` discipline; ADR practice; phase-gated workflow; "no fabricated functionality" principle.
- The heading-style registry (as the tokenizer layer under parser v2).
- Choice of `gpt-5-mini` + `text-embedding-3-small` — right cost/quality tier for this project; only note the reasoning-token budget behavior (observed live: 64 hidden tokens for a one-word answer) in prompt design.

## 14. Priority Roadmap

| # | Milestone | Goal | Key deliverables | Risks | Success criteria | Commit boundary | Deploy impact |
|---|---|---|---|---|---|---|---|
| M0 | Hardening & alignment | Close C1, C4, C5; ingest full corpus | product.md decision recorded (ADR); warnings wired + tested; CLI test isolated; 3 remaining docs ingested; dataset manifest committed | Product decision stalls | All 4 docs processed; CI green; warnings visible in manifests | 1–2 commits | None |
| M1 | Parser v2 | Outline state machine | New resolution layer; golden trees for all 4 docs; ADR-0012 | Over-engineering; regressions | Correct hierarchy on all 4 docs incl. Abraham cross-branch case | 1 commit + tag | None |
| M2 | Spans + metadata | Exact reading order; case metadata | Adapter carries spans; case-law source metadata; manifest linkage | Schema-extension mistakes | Reading order exact; citations resolvable to case names | 1 commit | None |
| M3 | Chunking | Typed, structure-aware chunks | `ChunkRecord` schema; chunker + tests; definition/table/recital handling | Chunk quality unmeasurable without M4 | Golden chunk fixtures for 4 docs | 1 commit | None |
| M4 | Index + retrieve + evaluate | Local RAG loop with proof | Embeddings; `RetrievalBackend` (Chroma+BM25); gold QA set (≥25 q); eval harness in CI | Eval set author bias | Retrieval hit-rate & citation accuracy baselined and reported honestly | 1–2 commits + tag | None |
| M5 | Grounded answering + UI | Citation-backed QA | Answer service (grounding rules, refusal path); Streamlit UI | Hallucination; reasoning-token budgets | Every answer cites real sections; refusal on no-evidence verified | 1–2 commits | Local only |
| M6 | Azure deployment | Production posture | PAYG upgrade; AI Search backend impl; Blob storage impl; App Service + Managed Identity + OIDC CI/CD; App Insights; Entra migration; disable local auth | Cost; auth migration bugs | Public demo URL; zero secrets in config; telemetry visible | Several commits + tag | Full |
| M7 | Extensions (optional) | Approved backlog | HTML ingestion (ADR-0011); semantic ranker eval; multi-vector summaries; contract-corpus expansion | Scope creep | Each shipped behind existing interfaces | Per feature | Incremental |

## 15. Estimated Production Readiness

- Ingestion subsystem: **~85%** (parser v2 + warnings wiring + full-corpus validation remaining).
- Platform overall vs. product promise: **~35%** — enrichment, retrieval, generation, evaluation, UI, and deployment do not exist yet. This is *phase-appropriate*, not alarming; the foundation quality means the remaining layers have a clean substrate.
- Honest time-to-demo (M0–M5): on the order of a few focused weeks at current pace. Time-to-deployed (M6): add subscription upgrade + one milestone.

## 16. What I Would Build Differently From Scratch

1. **Carry DI `spans`/offsets from day one** — the y-sort reading-order heuristic and the citation-anchoring gap both trace to dropping them.
2. **Define the corpus before the pipeline** — the PDF-only constraint silently pivoted the corpus away from the product spec; corpus-first design would have surfaced ADR-0011 as a phase-1 requirement or reshaped the product doc immediately.
3. **Evaluation harness before RAG, even before chunking** — gold questions written against raw documents anchor every downstream design choice.
4. **Entra ID from the first Azure call** — the `.env` detour was pragmatic but created a migration milestone that day-one `DefaultAzureCredential` would have avoided.
5. Request DI's markdown output (`output_content_format`) in parallel during validation — a cheap A/B source of structural signal for the parser.
6. Model the parser as an outline state machine from the start — heading-style thinking was the local optimum that live data invalidated.

## 17. What Should Be Preserved From The Existing Project

The entire architectural *method*: vendor isolation, interface seams, DI, typed errors, schema versioning, structured observability, phase gates, ADRs, and the habit — demonstrated repeatedly — of verifying against live systems instead of assuming. Also concretely: the `DocumentRecord` schema, the storage abstraction, the logging design, the exception taxonomy, the test suite, the CI, and the docs structure. This is the rare project where the review's main instruction is "keep doing exactly this, in this order, for the next six layers."

## 18. Final Recommendation

**Proceed — do not re-platform.** Fix alignment and the parser before building upward: resolve the product/corpus decision (C1), harden the small gaps (C4, C5), ship parser v2 as an outline state machine, extend the adapter with spans, then build the RAG stack as structure-aware parent-child retrieval over hybrid search behind a `RetrievalBackend` interface, evaluated by a gold QA harness before any UI work. Upgrade the subscription before the deployment milestone. Defer every fashionable technique (GraphRAG, agentic, Self-RAG, late interaction) — this corpus and product get more from correct citations than from exotic retrieval.
