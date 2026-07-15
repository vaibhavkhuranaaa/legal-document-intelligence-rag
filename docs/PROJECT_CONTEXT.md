# Project Context — Read This First In A New Chat

**Purpose of this file:** paste this (or point a new Claude session at it) to fully
re-orient without re-deriving history. It is self-contained — no prior
conversation needed. Last verified against live repo/Azure state: see
"Verification" at the bottom.

---

## 1. Overall Summary

**Legal Document Intelligence RAG** is a production-grade, portfolio-quality
Retrieval-Augmented Generation platform built end-to-end on Azure. It ingests
real legal PDFs through Azure Document Intelligence, reconstructs their
section hierarchy, chunks and embeds them, retrieves relevant passages via
hybrid search, and answers questions with **citations resolved to exact
case/section/page** — refusing to answer when the corpus doesn't support it.

It was built in disciplined phases (bootstrap → ingestion pipeline → live
Azure validation → RAG demo), each phase verified against real Azure services
before the next began, with ADRs recording every non-trivial decision. The
demo is **working today**, validated with real questions against a real
14-document, 1,133-page corpus.

**Repository:** `github.com/vaibhavkhuranaaa/legal-document-intelligence-rag`
(currently **private**; safe to make public — no secrets are tracked, corpus
is entirely public court documents).

## 2. Overall Use Case

**Who it's for:** demonstrates AI/ML engineering competency for legal-tech,
eDiscovery, and enterprise RAG roles — specifically: building trustworthy
LLM systems over long, structurally complex, high-stakes documents where
hallucination is unacceptable.

**What it actually does:** a user (or interviewer) asks a natural-language
question about M&A-related Delaware court opinions — e.g. *"Why did the
plaintiff in Abraham v. Wirtz fail to get a quasi-appraisal remedy?"* — and
receives an answer grounded in retrieved passages, with every claim citing a
numbered source that resolves to a real case name, section heading, and page
number. Questions outside the corpus are refused, not hallucinated (verified
live: asked about an unrelated acquisition, the system correctly declined and
flagged the answer as ungrounded).

**Why this is a good portfolio piece:**
- Real Azure services end-to-end (Document Intelligence, Azure OpenAI), not
  mocked — every capability claimed has been verified with a live API call.
- Production engineering discipline: vendor SDK isolation, dependency
  injection, typed errors, versioned schemas, structured logging, 147 tests,
  CI, 12 ADRs documenting *why*, not just *what*.
- Honest documentation: known limitations are written down, not hidden (e.g.
  the parser's residual heuristic limitations, the corpus/product-scope
  decision, the Free Trial subscription constraint).
- A genuine, self-conducted architecture review (`ARCHITECTURE_REVIEW.md`)
  scoring the platform 7.5/10 and prescribing exactly what to build next —
  demonstrates CTO-level systems thinking, not just implementation.

## 3. Current State (verified working)

| Layer | Status | Evidence |
|---|---|---|
| Ingestion pipeline | ✅ Complete, validated | 14/14 public corpus documents processed, 0 failures |
| Azure infrastructure | ✅ Provisioned, live | `rg-legal-rag-dev` (East US): `di-legal-rag-dev` (Document Intelligence, S0), `oai-legal-rag-dev` (Azure OpenAI, S0) with `gpt-5-mini` (10K TPM) and `text-embedding-3-small` (100K TPM) deployed |
| Chunking + embeddings | ✅ Complete, validated | 1,468 chunks indexed from the real corpus |
| Hybrid retrieval | ✅ Complete, validated | Chroma (vector) + BM25 (lexical), RRF-fused |
| Grounded answering | ✅ Complete, validated live | Correct, well-cited answers on real legal questions; refusal path confirmed working |
| Flask research workspace | ✅ Live | Research, Evidence, Corpus, Evaluation, and health routes on Azure App Service |
| Tests / CI | ✅ 150 passing, lint clean | `uv run pytest`, `uv run ruff check .` |
| Production adapters | ✅ Implemented, unit-tested | Managed identity, Blob Storage, and Azure AI Search adapters |
| Deployment infrastructure | ✅ Release-ready | Production resource group, identity, Storage, Blob container, AI Search, and the 1,468-chunk public corpus are live |
| App Service public host | ✅ Live | Flask/Gunicorn at the repository's public demo URL |
| Parser v2 (outline state machine) | ❌ Not started | Current heading-style registry works but has known residual limitations (§6) |
| Evaluation harness | ✅ Release recorded | `gold-qa-v2-delaware-expansion`: 45 questions, 100% retrieval hit rate@8 and citation-provenance validity against the 1,468-chunk production index |

## 4. Architecture At A Glance

```
PDF corpus (public Delaware M&A litigation, 14 docs / 1,133 pages)
  → Azure Document Intelligence (prebuilt-layout, S0)
  → adapter (sole Azure-SDK boundary; nothing downstream touches SDK types)
  → outline parser (heading-style registry; deterministic ambiguity warnings)
  → DocumentRecord (versioned schema: section tree + flat cited elements)
  → structure-aware chunker (typed: text/table; footnote markers dropped;
    title + section path prepended to embed text)
  → Azure OpenAI embeddings (text-embedding-3-small)
  → hybrid retrieval: Chroma (dense) + BM25 (lexical), RRF-fused
  → grounded generation (gpt-5-mini; citation-required prompting)
  → Flask public research workspace / legal-rag-ask CLI
    (citations resolve to case/section/page/canonical source URL/checksum)
```

Code layout:
```
src/legal_rag/
├── ingestion/   # discovery → normalization → Azure DI client + adapter →
│                # outline parser → mapper → validation → storage → manifests
├── rag/         # chunking, embeddings, hybrid store, answer service, CLIs
└── ui/          # Flask research workspace
tests/           # 150 tests, no network calls, deterministic (fakes for Azure)
docs/            # this file, ADRs, roadmap, architecture review, product spec
data/            # dataset_manifest.json (committed); raw/processed/failed (gitignored)
```

## 5. How To Run

```bash
uv sync                                                   # env + deps
# .env must be populated (see .env.example) — not committed
uv run legal-rag-ingest                                   # PDFs -> structured JSON
uv run legal-rag-index                                    # chunk + embed + index
uv run legal-rag-ask "your question"                      # CLI Q&A
uv run flask --app legal_rag.ui.flask_app:app run --port 8503
uv run pytest                                              # 150 tests
uv run ruff check .                                        # lint
```

## 6. Known Limitations (documented honestly, not hidden)

1. **Parser is style-based, not outline-state-based.** Two deterministic
   failure modes remain on real documents: (a) bare numbered headings
   (`"1."`) reset to depth 1 regardless of context; (b) letter lists under
   *different* Roman-numeral parents can merge because matching is keyed by
   style name, not branch-scoped. Fix designed but not built: an outline
   state machine (`ARCHITECTURE_REVIEW.md` §8). Not blocking the demo.
2. **Product/corpus scope was realigned mid-project** (ADR-0012): original
   spec targeted SEC EDGAR filings (HTML — unsupported by the PDF-only
   pipeline); validated corpus is Delaware court opinions instead. Product
   scope now explicitly covers both; EDGAR ingestion is an approved,
   deferred future milestone (ADR-0011).
3. **Evaluation scope is intentionally narrow.** `gold-qa-v2-delaware-expansion` validates
   retrieval coverage and citation provenance, not legal-answer correctness;
   expand to attorney-reviewed answer/citation correctness only in a dedicated
   later evaluation phase.
4. **Production corpus is released.** `legal-rag-chunks-r2` contains the
   approved 1,468 public chunks; the prior 390-chunk index remains the rollback point.

## 7. How To Improve — Prioritized Roadmap

Full detail and reasoning: `docs/ARCHITECTURE_REVIEW.md` §14. Summary,
highest-value first:

1. **Parser v2: outline state machine.** Replaces style-name matching with
   per-branch enumerator-value tracking and successor prediction. Fixes both
   known residual limitations (§6.1). Pure-logic change, no schema impact,
   moderate effort (see `ARCHITECTURE_REVIEW.md` §8 for the exact design).
2. **Carry Azure DI `spans` through the adapter.** Currently reading order
   is inferred by y-coordinate sort because span offsets are discarded on
   ingestion — carrying them through gives exact reading order and an exact
   text anchor per element for free (useful for future citation
   highlighting). Small, additive schema extension.
3. **Ingest real SEC EDGAR transaction documents** (ADR-0011) — extends the
   corpus to match the original product vision (merger agreements, S-4s),
   not just litigation about mergers. Requires an HTML→structured-content
   path (two designed options in ADR-0011: convert-to-PDF vs. native HTML
   parser feeding the existing `RawDocument` model).
4. **Secure user-upload eDiscovery workflow.** Requires authenticated
   workspaces, private Blob storage, malware scanning, asynchronous ingestion,
   user-scoped retrieval, quotas, retention/deletion, and audit logging.
6. **Smaller, opportunistic items:** raise the reasoning-token budget
   awareness in prompts (gpt-5-mini spends hidden tokens — observed 64 for
   a one-word reply); add `pytest-cov` + `mypy` (deferred by ADR-0003 until
   the codebase had enough surface area — it now does); expand corpus
   diversity beyond Delaware appraisal cases once EDGAR ingestion lands.

## 8. Engineering Principles To Preserve

These are load-bearing for why this project is a strong portfolio piece —
don't undo them while improving things:

- Vendor SDKs isolated behind adapters; business logic never touches Azure
  SDK types directly (ADR-0004).
- Every component receives dependencies by injection; one construction
  point per subsystem (`cli.py`, `index_cli.py`, `ask_cli.py`).
- Configuration loaded exactly once, behind a single settings accessor
  (ADR-0008) — never read `os.environ` ad hoc.
- Schemas are versioned and additive; `DocumentRecord` stays frozen, new
  concerns (chunks) get their own schema referencing it by ID.
- One phase verified against live Azure services before the next begins.
  Never claim something works without having actually run it.
- Every non-trivial decision gets an ADR in `docs/decisions.md` — currently
  12, covering everything from `uv` adoption to the corpus-scope pivot.

## 9. Document Map

| File | Contents |
|---|---|
| `docs/PROJECT_CONTEXT.md` | **This file** — start here in a new session |
| `docs/product.md` | Product vision, target users, use cases, non-goals |
| `docs/roadmap.md` | Phase-by-phase status (currently: Phase 3 deployment) |
| `docs/deployment.md` | Deployment runtime, data-release, and verification runbook |
| `docs/decisions.md` | All 12 ADRs — the *why* behind every major choice |
| `docs/PHASE1_SUMMARY.md` | Deep-dive on the ingestion pipeline's architecture |
| `docs/ARCHITECTURE_REVIEW.md` | Full CTO-level review: scores, findings, target architecture, prioritized roadmap |
| `docs/SUMMARY_FOR_CHATGPT.md` | Condensed version of the review for independent critique |
| `data/dataset_manifest.json` | Source-of-truth registry for the 4-document corpus (checksums, provenance, case metadata) |

## 10. Verification

This file's claims were checked against live state on 2026-07-15: `git log`,
`uv run pytest` (147 passed), `uv run ruff check .`, and Flask browser/Azure
smoke tests. Azure production has the public Flask App Service, managed identity,
private Blob container, Basic AI Search service, production Search index, and
390 published chunks. Re-run these checks rather than trusting this table
blindly — it is a snapshot, not a live view.
