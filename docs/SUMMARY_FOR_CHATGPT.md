# SUMMARY_FOR_CHATGPT.md

**Purpose:** Independent architecture critique requested before implementation. Written by the reviewing architect for a second Principal AI Architect. Full review: `docs/ARCHITECTURE_REVIEW.md`. All factual claims are grounded in the repository and live Azure validation runs, not projections.

## 1. System as it exists

Python 3.12 / `uv` monorepo, `src/legal_rag/ingestion/` with 14 modules: discovery → normalization → Azure Document Intelligence (`prebuilt-layout`, S0) → adapter (sole Azure-SDK boundary) → heading-style outline parser → mapper → semantic validation → storage abstraction (local FS impl) → per-run manifests + structured JSON logging (contextvars-based). Versioned `DocumentRecord` schema with a **dual representation**: a nested section tree (`structure`) and a flat, citation-addressable element list (`elements`, each carrying `section_path`, page, bounding regions). 115 tests; CI; ADR-0001–0011. Azure: Document Intelligence S0 + Azure OpenAI (`gpt-5-mini` 2025-08-07 GlobalStandard, `text-embedding-3-small`), East US, validated live on a 34-page Delaware Chancery opinion (all pages, 185 elements, schema-valid, correct SHA-256 provenance). Auth is currently API-key/`.env` by explicit interim decision; Entra/Managed Identity migration is already agreed for the deployment phase. Nothing beyond ingestion exists yet (no chunking/embeddings/retrieval/RAG/UI) — deliberately phase-gated.

## 2. Final proposed architecture

Ingestion (existing, hardened) → **structure-aware chunker** (new `ChunkRecord` schema referencing `element_ids`; typed chunks: clause / definition / table / recital; parent = section, child = ~250–500-token paragraph runs; section-path prefix prepended to embed-text) → embeddings (`text-embedding-3-small`) → **`RetrievalBackend` interface** (dev: Chroma + BM25 with rank fusion; prod: Azure AI Search hybrid + built-in semantic ranker) → **parent-child retrieval with metadata filtering** → grounded generation (`gpt-5-mini`; citation-required prompting; model cites chunk IDs, app resolves to human citations; explicit refusal path) → **gold-QA evaluation harness as a CI gate before UI** → Streamlit on App Service, user-assigned Managed Identity, Blob-backed `StorageBackend` impl, App Insights via the existing logging seam, OIDC-based GitHub Actions deploy.

## 3. Major redesigns proposed (only two touch existing code)

**R1 — Parser v2: heading-style matcher → outline state machine.**
Live validation proved the current parser reasons about heading *styles*, not outline *state*. Two deterministic failures on real data: (a) bare `"1."` enumerators reset to absolute depth 1 (fabricating top-level sections); (b) letter lists under different parents merge, because matching keys on style *name* with no branch scoping. Proposed model: per-open-branch state tracking enumerator kind **and current value**, resolving each new heading against predicted legal successors (after `II.A.1`: `2` sibling, `B` parent-sibling, `III` grandparent-sibling, or new child). This is branch-scoped by construction and disambiguates single-character Roman/letter collisions (`C.` after `B.` is a letter; `III.` after `II.` is Roman) via sequence continuity. Keep the existing style registry as the tokenizer layer. Rejected alternatives: grammar parser (legal headings aren't a stable grammar across courts/filers), LLM structuring (nondeterministic + unauditable for a component whose product value *is* deterministic citations). No schema change.

**R2 — Adapter carries Azure DI `spans` (character offsets).**
The adapter currently discards spans; reading order is then reconstructed by a y-coordinate sort — a documented limitation that exists *only because* the exact ordering information was dropped. Carrying offsets gives exact reading order and an exact text anchor per element (future citation highlighting). Additive schema extension.

Everything else is greenfield layered behind interfaces matching the project's established pattern.

## 4. Key decisions + tradeoffs

| Decision | Tradeoff accepted |
|---|---|
| Parent-child + hybrid (BM25+vector) + metadata filters; **reject** GraphRAG, agentic, Self-RAG, late interaction, compression for v1 | Less impressive buzzword surface; but the product is precision clause/holding lookup with citations over a small, deeply structured corpus — hierarchy already exists in the schema, so hierarchical RAG is nearly free, and legal queries are exact-term-heavy (statute cites, defined terms) making BM25 essential |
| AI Search built-in semantic ranker instead of self-hosted cross-encoder | Possible relevance ceiling; zero extra infrastructure — revisit only if eval shows the ceiling |
| Dev/prod retrieval parity via one interface, two backends (Chroma+BM25 / AI Search) | Two implementations to maintain; mirrors the already-proven `StorageBackend` pattern |
| Evaluation harness (≥25 gold QA, retrieval hit-rate + citation accuracy + faithfulness) is a **gate before UI** | Slower to demo; prevents shipping an unmeasured RAG system |
| No fixed-size chunking; structure-typed chunks with token caps only as overflow | Chunker complexity; fixed-size would destroy the section/citation alignment the whole product depends on |
| Keep `gpt-5-mini` / `text-embedding-3-small` | gpt-5-mini spends hidden reasoning tokens (observed: 64 for a one-word reply) — prompt budgets must be generous |

## 5. Critical non-code findings (need decisions, not designs)

**C1 — Product/corpus drift (top finding).** `product.md` promises an M&A / SEC EDGAR platform (8-Ks, S-4s, merger agreements). The validated corpus is Delaware Chancery *court opinions*, adopted because EDGAR serves HTML and the pipeline is PDF-only (HTML ingestion is ADR-0011, deliberately deferred). Different structure, different user questions, different chunk types. Recommended: broaden product scope to "M&A transaction documents and related litigation" now, add a few manually-converted EDGAR agreements as stopgap corpus, keep HTML ingestion as the approved later milestone. **Must be decided before chunk/eval design.**

**C2 — Azure Free Trial subscription with hard spending limit.** Deployment (~$100/mo: App Service B1 + AI Search Basic + usage) is impossible on it; usage halts when credit exhausts. Pay-As-You-Go upgrade must be scheduled before the deployment milestone.

Smaller confirmed items: parser ambiguity warnings exist but aren't persisted into output metadata (one wiring gap); one CLI test fails from real-`.env` leakage and incidentally performs a paid Azure call; corpus metadata schema is EDGAR-shaped (always null) while actual corpus is case law; curated dataset manifest isn't linked to pipeline outputs.

## 6. Roadmap (each milestone = commit boundary, tested, tagged where noted)

M0 hardening + product decision + full 4-doc corpus → M1 parser v2 (tag) → M2 spans + case metadata → M3 chunking → M4 embeddings + retrieval + **eval baseline** (tag) → M5 grounded answering + Streamlit → M6 PAYG upgrade + Azure deployment + Entra migration + disable local auth (tag) → M7 optional: HTML ingestion, semantic-ranker eval, multi-vector summaries.

## 7. Unresolved questions for the second reviewer

1. Is dev/prod retrieval parity (Chroma+BM25 fusion locally) worth the dual-backend cost, or should dev go straight to AI Search Free tier (50 MB — fits this corpus; lacks semantic ranker) and eliminate Chroma entirely?
2. Faithfulness judging: only `gpt-5-mini` is deployed. Self-judging is weak. Deploy a stronger judge model for eval runs, or accept human spot-checking at this corpus size?
3. Parser v2 scope: is successor prediction over 7 enumerator kinds sufficient, or should it also consume DI's markdown output (`output_content_format="markdown"`) as a second structural signal? (Adds an Azure coupling to the parser's inputs.)
4. Should cross-reference resolution ("as defined in Section 1.1") stay metadata-only in v1, or is definition-chunk linking cheap enough to include at M3?
5. `ChunkRecord` placement: separate schema/file (proposed, keeps `DocumentRecord` frozen) vs. embedding chunks inside `DocumentRecord` (single artifact, but couples ingestion schema to RAG concerns)?

## 8. Risks

- Parser v2 over-engineering — mitigated by golden-tree fixtures from the 4 real documents as the acceptance bar.
- Eval-set author bias (same person writes questions and system) — mitigated partially by citation-accuracy metrics being objective.
- Corpus of 4 documents limits how much any retrieval comparison can claim — report honestly, never extrapolate.
- gpt-5-mini reasoning-token consumption inflating latency/cost under RAG prompts — measure at M4 before committing budgets.
- Free Trial credit exhaustion mid-development (spending limit halts, not overbills) — monitor via Cost Management API (verified working).

**Bottom line for the reviewer:** the foundation is unusually disciplined and should not be re-platformed. Critique wanted primarily on: the parent-child + hybrid retrieval choice vs. alternatives (§4), the parser state-machine design (§3 R1), the five open questions (§7), and anything the corpus-drift decision (C1) should change about chunk typing.
