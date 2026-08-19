# Deployment Runbook

This runbook records the production deployment contract. The Azure adapter code
and core data-plane resources exist; follow the current blocked/unblocked state
in [`roadmap.md`](./roadmap.md).

## Runtime contract

The public application serves a previously built search index and must never
ingest documents or create embeddings during a web request. The live runtime is
the Flask/Gunicorn research workspace.

Azure App Service on Linux uses [`startup.txt`](../startup.txt) as its custom
startup command:

```text
gunicorn --bind 0.0.0.0:8000 --timeout 120 legal_rag.ui.flask_app:app
```

The file is versioned so the same command is used in every environment. App
Service must be configured to use it as the startup command. The 120-second
Gunicorn worker timeout is intentional: a synchronous request performs Azure
AI Search and Azure OpenAI calls, which must not be killed by Gunicorn's
30-second default. The first process start after ZIP deployment can take about
a minute while Oryx prepares the environment; allow 90 seconds before treating
a startup check as failed.

`pyproject.toml` and `uv.lock` remain the dependency source of truth. The
root [`requirements.txt`](../requirements.txt) is a committed App Service
build artifact, generated whenever locked runtime dependencies change:

```bash
uv export --format requirements-txt --no-hashes --no-dev --output-file requirements.txt
```

App Service ZIP deployment must set `SCM_DO_BUILD_DURING_DEPLOYMENT=true` so
Oryx creates the Linux virtual environment from this file. Do not hand-edit
`requirements.txt`.

The release workflow builds the ZIP with `git archive` from the approved exact
revision, so caches, virtual environments, local data, and other untracked
files cannot enter the deployment artifact. Azure CLI runtime tracking is
disabled for the upload step because OneDeploy completion and application
startup are separate checks. After OneDeploy succeeds, the workflow stamps the
source revision, restarts the app, and verifies `/healthz` plus the public
research routes.

## Environment boundary

Local development uses `.env`, API keys, filesystem-backed processed records,
and Chroma. None of those local persistence assumptions are valid for App
Service.

The production App Service uses these settings with the corresponding Azure
implementations:

- user-assigned managed identity client ID;
- Azure OpenAI endpoint and deployment names;
- Azure AI Search endpoint and index name;
- Blob Storage account/container names;
- Application Insights connection string.

App settings and managed identity replace `.env` and production API keys. Do
not add secrets to this repository or to `startup.txt`.

`RETRIEVAL_BACKEND=azure_ai_search` and `STORAGE_BACKEND=azure_blob` select the
production adapters. Their Azure resources and RBAC assignments are provisioned
in the production resource group; retain `chroma` and `local` for development.

The promoted production index is named `legal-rag-chunks-r3`. It is the only
retained search index. It exposes these fields: `chunk_id` (key), document
and citation metadata, `text`/`embed_text` (searchable), `embedding` (vector),
and the collection fields `section_path` and `element_ids`. Index provisioning
is intentionally separate from application startup, so a web request cannot
mutate search infrastructure.

Current resources are in `rg-legal-rag-prod`. The `asp-legal-rag-prod` Linux B1
plan, `app-legal-rag-prod-278f1d` web app, `id-legal-rag-prod` user-assigned
identity, and `stlegalragprod278f1d` private storage account are in East US.
The `srch-legal-rag-sls-278f1d` Serverless Developer Search service is in West
Central US. Its promoted index contains the approved 3,055 public chunks
(1,468 Delaware opinion chunks and 1,587 SEC agreement chunks).

Serverless Developer is a public preview with no service-level agreement and
is not recommended by Microsoft for production workloads. It was selected for
this low-volume public demonstration because compute can scale to zero when
idle. Search billing is deferred during the initial preview; Microsoft states
that it will provide at least 30 days notice before billing begins. After that,
compute and indexed storage are usage-based and must be monitored. The prior
Basic Search service and its r2 and legacy indexes were deleted after exact
document parity, hybrid-result parity, live evidence parity, and generated
answer citation checks passed. Recovery now requires rebuilding a versioned
index from the approved corpus artifacts rather than switching to r2.

## Corpus release procedure

Each corpus update is a versioned operator operation, independent of web-app
deployment:

1. Register the public source, provenance, and checksum in
   `data/dataset_manifest.json`.
2. Run ingestion against the controlled source location.
3. Validate the structured records and inspect failures/warnings.
4. Build the production retrieval index from the validated records.
5. Run `legal-rag-validate-corpus --check-urls`; reject the release if a
   canonical public source is unavailable.
6. Run `legal-rag-evaluate` against the configured production index and review the written
   report before publishing aggregate metrics to `data/evaluation/latest.json`.
7. Run retrieval and citation smoke tests against the configured production index.
8. Promote the index only after the checks pass; record its manifest/version.

The public app continues to serve the last promoted index if a corpus release
fails.

## Release checks

Before a deployment release:

```bash
uv run ruff check .
uv run pytest
```

After deployment, verify that the app loads, reports a nonzero indexed-chunk
count, answers a known corpus question with citations, and refuses an unrelated
question. Check App Service logs and Application Insights for startup or
dependency failures.

Also verify `/healthz`, `/corpus`, `/evaluation`, and an Evidence card's
canonical PDF page link. The live URL must remain unchanged.
