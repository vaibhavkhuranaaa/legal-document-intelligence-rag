# Legal Document Intelligence RAG

Production-grade Retrieval-Augmented Generation (RAG) system over a public legal
document corpus, built on Azure. This is a portfolio project demonstrating
end-to-end AI engineering: document ingestion, retrieval, and generation, deployed
as a working web application.

## Status

**Phase 0 — Repository bootstrap.** No application functionality exists yet. This
repository currently contains only the project foundation (structure, dependency
management, linting, test harness). See [docs/roadmap.md](docs/roadmap.md) for
what's planned, [docs/architecture.md](docs/architecture.md) for the system
design as it's built out, and [docs/decisions.md](docs/decisions.md) for why
things are set up the way they are.

## Data source policy

This project uses **public, non-confidential legal documents only** (e.g.,
CourtListener bulk opinions, SEC EDGAR filings). No real client, firm, or case
data is ever used, so the repository and its contents are safe to be public.

## Planned stack

- **Language:** Python 3.12
- **Document parsing:** Azure Document Intelligence
- **LLM / embeddings:** Azure OpenAI
- **Orchestration:** LangChain
- **Vector store:** Chroma (development), Azure AI Search (future production option)
- **UI:** Streamlit
- **Deployment:** Azure App Service

## Project structure

```
.
├── src/legal_rag/     # Application package (empty in Phase 0)
├── tests/             # Test suite
├── docs/              # Architecture, roadmap, and decision records
├── pyproject.toml     # Single source of truth for dependencies and tooling config
└── .env.example       # Documented environment variables (no real secrets)
```

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/) installed. `uv` manages the Python
3.12 interpreter and virtual environment itself — no system Python is touched.

```bash
# Create the virtual environment and install dependencies (including dev tools)
uv sync

# Run the test suite
uv run pytest

# Run the linter
uv run ruff check .
```

Copy `.env.example` to `.env` and fill in real Azure credentials once later
phases require them. `.env` is never committed.

### Continuous integration

Every push and pull request to `main` runs lint (`ruff check`) and the test
suite (`pytest`) via GitHub Actions — see
[.github/workflows/ci.yml](.github/workflows/ci.yml).

## Principles

- Production-quality code and structure from the first commit.
- No placeholder implementations, no fabricated functionality or metrics.
- Secrets are never hardcoded; all configuration flows through environment
  variables (see `.env.example`).
- Work proceeds one approved phase at a time; tradeoffs are documented in
  [docs/decisions.md](docs/decisions.md) before major changes.

## License

[MIT](LICENSE)
