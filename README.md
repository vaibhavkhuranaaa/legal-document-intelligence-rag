# Legal Document Intelligence RAG

[![CI](https://github.com/vaibhavkhuranaaa/legal-document-intelligence-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/vaibhavkhuranaaa/legal-document-intelligence-rag/actions/workflows/ci.yml) ![Publication](https://img.shields.io/badge/publication-review_required-5b6470) ![Production claim](https://img.shields.io/badge/production_claim-no-18794e)

> A deployed Azure RAG research workspace for citation-grounded questions over public M&A litigation and transaction documents.

## Executive overview

| Question | Reviewed fact |
| --- | --- |
| Problem | How can legal research return an evidence-linked answer without wandering beyond an approved public corpus? |
| Intended user | A legal-technology reviewer or AI engineering hiring manager evaluating trustworthy document retrieval and deployment practices. |
| Decision supported | Whether the public corpus contains retrievable, traceable evidence for the research question. |
| Outcome | A versioned public-document pipeline turns court opinions and SEC filings into 3,055 searchable chunks and returns evidence-linked answers with an explicit refusal path. |
| Try it | [Open the reviewed demo](https://app-legal-rag-prod-278f1d.azurewebsites.net/) |
| Important boundary | Uses public court opinions and public SEC transaction documents. The application provides legal information for engineering demonstration and is not legal advice. |

## What the system does

- Public source registration and checksum validation
- Azure Document Intelligence and native SEC HTML extraction
- Structure-aware chunking and embeddings
- Azure AI Search retrieval
- Citation-required grounded generation and refusal
- Read-only Flask research workspace on Azure App Service

## Visual architecture

![System architecture showing a legal researcher, registered public court and SEC sources, checksum validation, extraction, chunk storage, Azure AI Search, Azure OpenAI, managed identity, observability, deployment, cited output, and evaluation.](portfolio/assets/system.svg)

Canonical editable source: [`architecture/system.mmd`](architecture/system.mmd). The SVG and PNG are deterministic generated assets; `system.freshness.json` records their source hash and renderer.

## End-to-end workflow

- Ask a question about a document in the registered public corpus
- Review the grounded answer or explicit refusal
- Open the numbered citations and inspect case, section, page, and canonical source
- Compare release metrics with the committed evaluation artifact

## Technology stack

| Technology | Role | Asset provenance |
| --- | --- | --- |
| <img src="portfolio/assets/technology/python.svg" width="20" height="20" alt="" /> Python | Application, adapters, and evaluation language | Simple Icons 16.27.0 (CC0-1.0) |
| <img src="portfolio/assets/technology/flask.svg" width="20" height="20" alt="" /> Flask | Read-only research workspace | Simple Icons 16.27.0 (CC0-1.0) |
| Azure Document Intelligence | Public PDF extraction | Visible text fallback; no approved local logo registered |
| Azure OpenAI | Evidence-constrained answer generation | Visible text fallback; no approved local logo registered |
| Azure AI Search | Promoted public-corpus retrieval index | Visible text fallback; no approved local logo registered |
| Azure Blob Storage | Versioned public document storage | Visible text fallback; no approved local logo registered |

## Quick start

### Install and verify

```bash
uv sync --all-extras
uv run ruff check .
PYTHONPATH=src uv run pytest -q
```

### Run the local workspace

```bash
uv run flask --app legal_rag.ui.flask_app:app run --port 8503
```

### Review release evidence

```bash
python -m json.tool data/evaluation/latest.json
python -m json.tool portfolio/project.json
```

## Demonstration workflow

**Ask a legal research question and inspect the evidence**

- Ask a question about a document in the registered public corpus
- Review the grounded answer or explicit refusal
- Open the numbered citations and inspect case, section, page, and canonical source
- Compare release metrics with the committed evaluation artifact

## Evaluation

| Measure | Dataset / scope | Method | Evidence | Limitation |
| --- | --- | --- | --- | --- |
| retrieval hit rate@8: 1.0 | 45-question gold-qa-v2-delaware-expansion benchmark over the promoted 3,055-chunk public index | Run the versioned gold-qa-v2-delaware-expansion evaluation against the configured promoted retrieval index. | [evaluation.release-v2](data/evaluation/latest.json) | The benchmark measures retrieval hit rate and citation provenance, not legal-answer correctness. |
| public retrieval chunks: 3,055 | Promoted r3 Azure AI Search corpus with r2 retained for rollback. | Review the versioned source registry, checksums, production index inventory, and documented environment boundary. | [disclosure.public-corpus](data/dataset_manifest.json and docs/deployment.md) | The public endpoint is anonymous and does not have the controls required for confidential legal matters. |

Evaluation mode: **versioned integration evaluation against the promoted public retrieval index plus a live reachability observation**. These results are project evidence, not a production SLO.

## Data disclosure

| Classification | Source | Permitted use | Excluded data |
| --- | --- | --- | --- |
| public | Official public Delaware court opinions and public SEC transaction documents registered with source URLs and checksums | Read-only portfolio demonstration, retrieval evaluation, and engineering research with source attribution | Client, firm, user-uploaded, confidential, privileged, and personal matter data; Private credentials, local environment files, and raw authorization material; Legal opinions, attorney work product, and production discovery decisions |

License / provenance: Public official-source documents; source-specific terms and United States government/public-record status apply

## Security and privacy boundaries

| Control | Implementation | Evidence | Known limitation |
| --- | --- | --- | --- |
| Registered public-source boundary | Every corpus document is registered with its canonical public URL and checksum before extraction. | [disclosure.public-corpus](data/dataset_manifest.json and docs/deployment.md) | Public availability does not make every source term identical; source-specific reuse terms still apply. |
| Managed identity | The deployed application authenticates to Azure resources without committed application credentials. | [deployment.azure-root](evidence/deployment/live-check.json) | Managed identity does not turn the anonymous interface into a confidential legal-matter system. |
| Citation-required generation | Answers are generated only from retrieved public evidence and retain source, section, page, and checksum provenance. | [evaluation.release-v2](data/evaluation/latest.json) | Retrieval and provenance metrics do not establish attorney-reviewed answer correctness. |

## Deployment state

| Provider | Runtime | State | Exposure | Verified | Production claim |
| --- | --- | --- | --- | --- | --- |
| Azure | Flask and Gunicorn on Azure App Service with managed identity, Azure AI Search, and Blob Storage | live | anonymous | 2026-07-23T20:57:44Z | No |

## Technology decisions and trade-offs

| Decision | Why | Alternative | Trade-off |
| --- | --- | --- | --- |
| Azure AI Search with Azure OpenAI | Managed retrieval, identity, and model services support a deployable Azure reference architecture. | Local Chroma and API-key based model access | The managed path improves deployment boundaries but costs more and requires explicit corpus-index promotion. |
| Vendor-neutral extraction records | Azure SDK objects terminate at the adapter so parsing, chunking, evaluation, and storage remain testable. | Propagate Azure SDK types through the pipeline | The stable boundary adds mapping code but reduces provider coupling and keeps tests deterministic. |

## Cost boundaries

| Component | Boundary | Implication |
| --- | --- | --- |
| Azure AI Search and Azure OpenAI | Owner-managed Azure services with a promoted 3,055-chunk public index. | Managed retrieval and model calls incur cloud cost and require explicit index-release coordination. |
| Azure App Service and Blob Storage | Read-only anonymous portfolio demonstration over public documents. | Confidential uploads, retention, malware scanning, and production monitoring are outside the approved scope. |

## Known limitations

- The public endpoint is anonymous and does not have the controls required for confidential legal matters.
- The evaluation does not establish legal-answer correctness or legal advice quality.
- Some source-specific reuse terms may differ even though the documents are available from official public sources.
- HTTP reachability does not establish an availability, confidentiality, security, or production SLO.

## Scalability roadmap

- Add attorney-reviewed answer and citation-correctness evaluation beyond retrieval and provenance checks
- Replace the residual style-based legal-outline parser heuristics with a branch-aware outline state machine
- Add authenticated matter isolation, encrypted private storage, malware scanning, retention, and audit controls before any user uploads
- Move ingestion and index construction to durable background workflows with reviewed index promotion
- Add quota, cost, abuse, availability, and security monitoring appropriate to an owner-approved production service

## Repository structure

| Path | Purpose |
| --- | --- |
| `src/` | Typed ingestion, extraction, chunking, retrieval, generation, and web application code. |
| `data/dataset_manifest.json` | Canonical public-source registry and checksums. |
| `data/evaluation/latest.json` | Versioned release evaluation evidence. |
| `architecture/system.mmd` | Canonical editable architecture source. |
| `portfolio/` | Public evidence manifest and generated presentation assets. |
| `docs/` | State, handoff, deployment, decisions, architecture, and release records. |

## Reproduction and verification

| Check | Command | Evidence |
| --- | --- | --- |
| Lint | `.venv/bin/python -m ruff check .` | Command output |
| Tests | `PYTHONPATH=src .venv/bin/python -m pytest -q` | [test.repository-suite](docs/STATE.md) |
| Manifest JSON | `.venv/bin/python -m json.tool portfolio/project.json >/dev/null` | Command output |

## Evidence index

| ID | Kind | Claim | Method | Result |
| --- | --- | --- | --- | --- |
| [`evaluation.release-v2`](data/evaluation/latest.json) | evaluation | The 45-question release benchmark recorded retrieval hit rate@8 1.0 and citation-provenance validity 1.0. | Run the versioned gold-qa-v2-delaware-expansion evaluation against the configured promoted retrieval index. | retrieval 1.0 / citation provenance 1.0 |
| [`deployment.azure-root`](evidence/deployment/live-check.json) | deployment | The current Azure App Service application root returned HTTP 200. | Read-only HTTP request with redirects followed; no user data submitted. | true |
| [`disclosure.public-corpus`](data/dataset_manifest.json and docs/deployment.md) | disclosure | The deployed retrieval corpus is derived from registered public court and SEC sources, not confidential client documents. | Review the versioned source registry, checksums, production index inventory, and documented environment boundary. | public |
| [`test.repository-suite`](docs/STATE.md) | test | The repository test suite passed locally when source import resolution was made explicit. | Run `PYTHONPATH=src .venv/bin/python -m pytest -q` after detecting stale editable-install paths in the generated virtual environment. | 178 passed |

## License and attribution

Source code is MIT licensed. Public documents retain their source-specific terms and attribution.

Technology marks are local copies generated from the pinned Simple Icons package where a canonical mark is available; every mark has a visible text label. Mermaid-generated architecture assets are derived from the canonical source in this repository.
