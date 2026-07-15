# Legal Document Intelligence RAG

A production-grade **Legal Document Intelligence platform** built on Azure: real
court documents go in as PDFs, and citation-backed answers come out — every claim
grounded in a retrieved passage with the exact case, section, and page number.

> **[Open the live demo →](https://app-legal-rag-prod-278f1d.azurewebsites.net/)**

> **Picking this project back up (including in a new AI chat session)?** Read
> [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) first — a self-contained
> summary, use case, current state, and prioritized "how to improve" roadmap.

Built as an AI engineering portfolio project demonstrating the full lifecycle:
document ingestion via Azure Document Intelligence, structure-aware chunking,
hybrid retrieval (vector + BM25), and grounded generation via Azure OpenAI —
with production engineering throughout (typed schemas, dependency injection,
structured logging, per-document failure isolation, 139 tests, CI, and eleven
Architecture Decision Records).

## What it does

Ask a question about the corpus of Delaware M&A litigation:

```
$ legal-rag-ask "Why did the plaintiff in Abraham v. Wirtz fail to get a quasi-appraisal remedy?"

Because he failed to perfect his statutory appraisal rights. The court held
that "Having failed to perfect his appraisal rights, Plaintiff is not
entitled to a quasi-appraisal remedy." [1][5] ...

Sources:
  [1] Abraham v. Estate of Wirtz (Del. Ch. 2025) — 3. Having Failed To
      Perfect His Appraisal Rights ... (p. 20)
  [4] Abraham v. Estate of Wirtz (Del. Ch. 2025) — 2. Plaintiff Made A
      Demand For Appraisal But Failed To Perfect His Rights ... (p. 17)
```

Questions outside the corpus are **refused, not hallucinated** — the model must
cite retrieved passages or say the documents don't contain the answer.

## Architecture

```
PDF corpus (public Delaware M&A litigation)
  → Azure Document Intelligence (layout extraction, S0)
  → vendor-neutral adapter (Azure SDK types never escape it)
  → legal-outline parser (heading-style registry + ambiguity warnings)
  → versioned DocumentRecord schema (section tree + flat cited elements)
  → structure-aware chunking (typed: text/table, section-path context)
  → Azure OpenAI embeddings (text-embedding-3-small)
  → hybrid retrieval: Chroma vector + BM25 lexical, RRF-fused
  → grounded generation (gpt-5-mini, citation-required prompting)
  → Streamlit UI / CLI with resolved case–section–page citations
```

Key engineering decisions are documented as ADRs in
[docs/decisions.md](docs/decisions.md); the full system review lives in
[docs/ARCHITECTURE_REVIEW.md](docs/ARCHITECTURE_REVIEW.md).

## Corpus

Four public Delaware M&A opinions (305 pages), registered with checksums and
provenance in [data/dataset_manifest.json](data/dataset_manifest.json):

| Case | Court | Pages |
|---|---|---|
| In re Appraisal of Dell Inc. (2015) | Del. Court of Chancery | 54 |
| Dell, Inc. v. Magnetar (2017) | Del. Supreme Court | 84 |
| HBK v. Pivotal Software (2023) | Del. Court of Chancery | 133 |
| Abraham v. Estate of Wirtz (2025) | Del. Court of Chancery | 34 |

**Public, non-confidential documents only.** No client, firm, or case data is
ever used. Output is legal information, not legal advice.

## Run the demo

Requires [`uv`](https://docs.astral.sh/uv/) and an Azure subscription with
Azure Document Intelligence + Azure OpenAI resources (see `.env.example` for
the required configuration; `.env` is never committed).

```bash
uv sync                                   # environment + dependencies
uv run legal-rag-ingest                   # PDFs -> structured JSON (Azure DI)
uv run legal-rag-index                    # chunk + embed + build hybrid index
uv run legal-rag-ask "your question"      # grounded Q&A in the terminal

uv run streamlit run src/legal_rag/ui/streamlit_app.py   # web demo
```

## Development

```bash
uv run pytest          # 139 tests, no network calls, deterministic
uv run ruff check .    # lint
uv run ruff format .   # format
```

Every push and PR to `main` runs lint + tests via GitHub Actions
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Deployment

The public Streamlit demo runs on Azure App Service with managed identity and
Azure AI Search. See [docs/deployment.md](docs/deployment.md) for the runtime
contract, data-release workflow, and release checks.

## Project structure

```
src/legal_rag/
├── ingestion/    # discovery, normalization, Azure DI client + adapter,
│                 # outline parser, schema mapping, validation, storage,
│                 # manifests, structured logging
├── rag/          # chunking, embeddings, hybrid store (Chroma+BM25),
│                 # grounded answer service, index/ask CLIs
└── ui/           # Streamlit demo app
tests/            # unit + pipeline tests (fakes for Azure/storage)
docs/             # ADRs, roadmap, phase summaries, architecture review
data/             # dataset manifest (committed) + corpus/outputs (gitignored)
```

## Engineering principles

- Production-quality code; no placeholder implementations, no fabricated
  functionality or metrics.
- Vendor SDKs isolated behind adapters; business logic never touches Azure
  types (ADR-0004).
- Every component receives dependencies by injection; configuration is loaded
  exactly once (ADR-0008).
- Secrets never hardcoded or committed; all configuration via environment.
- One verified phase at a time — each layer validated against live Azure
  services with real documents before the next is built.

## License

[MIT](LICENSE)
