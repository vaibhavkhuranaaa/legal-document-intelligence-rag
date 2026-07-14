# Deployment Runbook

This runbook records the production deployment contract. The Azure adapter code
and core data-plane resources exist; follow the current blocked/unblocked state
in [`roadmap.md`](./roadmap.md).

## Runtime contract

The public application is the Streamlit UI only. It serves a previously built
search index and must never ingest documents or create embeddings during a web
request.

Azure App Service on Linux uses [`startup.txt`](../startup.txt) as its custom
startup command:

```text
python -m streamlit run src/legal_rag/ui/streamlit_app.py --server.address 0.0.0.0 --server.port 8000
```

The file is versioned so the same command is used in every environment. App
Service must be configured to use it as the startup command.

`pyproject.toml` and `uv.lock` remain the dependency source of truth. The
root [`requirements.txt`](../requirements.txt) is a committed App Service
build artifact, generated whenever locked runtime dependencies change:

```bash
uv export --format requirements-txt --no-hashes --no-dev --output-file requirements.txt
```

App Service ZIP deployment must set `SCM_DO_BUILD_DURING_DEPLOYMENT=true` so
Oryx creates the Linux virtual environment from this file. Do not hand-edit
`requirements.txt`.

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

The production index is named `legal-rag-chunks`. It exposes these fields: `chunk_id` (key), document
and citation metadata, `text`/`embed_text` (searchable), `embedding` (vector),
and the collection fields `section_path` and `element_ids`. Index provisioning
is intentionally separate from application startup, so a web request cannot
mutate search infrastructure.

Current production resources are in `rg-legal-rag-prod` (East US): the
`asp-legal-rag-prod` Linux B1 plan, `app-legal-rag-prod-278f1d` web app,
`id-legal-rag-prod` user-assigned identity, `stlegalragprod278f1d` private
storage account, and `srch-legal-rag-prod-278f1d` Search service. The Search
index contains the currently approved 390 public chunks.

## Corpus release procedure

Each corpus update is a versioned operator operation, independent of web-app
deployment:

1. Register the public source, provenance, and checksum in
   `data/dataset_manifest.json`.
2. Run ingestion against the controlled source location.
3. Validate the structured records and inspect failures/warnings.
4. Build the production retrieval index from the validated records.
5. Run retrieval and citation smoke tests against the candidate index.
6. Promote the index only after the checks pass; record its manifest/version.

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
