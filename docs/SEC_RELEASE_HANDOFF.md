# SEC corpus-release handoff

Last updated: 2026-07-16

## Current safe state

- The public Flask app remains on `legal-rag-chunks-r2` with 1,468 Delaware
  opinion chunks. Do not change its index setting during this work.
- `legal-rag-chunks-r3` is staged only and has no promoted content.
- Six official SEC EX-2.1 inputs are checksum-registered in
  `data/dataset_manifest.json` as `approved_pending_ingestion`. Their local
  source and processed artifacts are ignored and must never be committed.

## Phase 6.1 completed locally

The initial r3 rehearsal did not reveal a general Azure capacity problem. It
revealed malformed release payloads:

- Before repair, 3,137 chunks contained 288,443,966 embedding characters; the
  largest was 2,516,683 characters from Broadcom/VMware.
- Cause one: HTMLParser does not apply browser implied-end-tag rules. An
  unclosed EDGAR `<p>` capture absorbed later document content and became a
  false heading/path. This is repaired in `ingestion/sec_edgar.py`.
- After the implied-block repair, genuine agreement paragraphs still exceeded
  the retrieval budget. `rag/chunking.py` now splits only individual SEC
  paragraphs, preferring legal sentence and list boundaries. It preserves the
  original text exactly, plus the document ID, element ID, full section path,
  official anchor, and enclosing source span.
- Some legacy SEC section paths are themselves too large to embed alongside
  source text. Their full value remains in `Chunk.section_path`; only the
  embedding context uses the most-specific suffix that fits the hard gate.
  No source text or citation metadata is truncated.
- `rag/chunking.py` now blocks any embedding payload above 8,000 characters
  before it can call Azure OpenAI. This guard is intentional and must remain.

## Local verification (2026-07-16)

- Regenerated all six ignored local SEC `DocumentRecord`s from the already
  downloaded approved inputs only. Each source checksum and generated document
  ID match `data/dataset_manifest.json`; all six records validate.
- The repaired SEC corpus contains **1,587 chunks**. Its largest `embed_text`
  is **7,999 characters**; the 8,000-character release gate passes.
- Ruff and the full test suite passed locally. No Azure indexing, evaluation,
  browser verification, app-setting change, or promotion was performed.

## Next approved phase: clean staged r3 rebuild

Use a new checkpoint; the old
`/private/tmp/legal-rag-r3-embeddings.json.gz` is incompatible with this
corpus build:

```bash
RETRIEVAL_BACKEND=azure_ai_search \
AZURE_SEARCH_INDEX_NAME=legal-rag-chunks-r3 \
AZURE_SEARCH_SOURCE_LOCATIONS_ENABLED=true \
uv run legal-rag-index \
  --embedding-checkpoint /private/tmp/legal-rag-r3-phase61-embeddings.json.gz
```

Before any promotion, confirm the clean r3 build, run the Azure-backed
evaluation, verify browser Evidence links against the official SEC sources,
and review all results. Production remains `legal-rag-chunks-r2` until each
gate passes.

## Do not do

- Do not promote r3, change the live app index, or publish SEC sources yet.
- Do not reuse `/private/tmp/legal-rag-r3-embeddings.json.gz` after chunk
  identities change.
- Do not solve the issue by truncating agreement text, inventing page numbers,
  or weakening the size gate.
