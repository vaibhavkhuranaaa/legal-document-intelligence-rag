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

# Requires the operator's real organization/contact identity; never invent one.
uv run legal-rag-validate-corpus --check-urls \
  --sec-user-agent "Organization contact@example.com"
```

Before any promotion, confirm the clean r3 build, run the Azure-backed
evaluation, verify browser Evidence links against the official SEC sources,
and review all results. Production remains `legal-rag-chunks-r2` until each
gate passes.

## Staged-release attempt (2026-07-16)

- A clean r3 rebuild completed using the new
  `/private/tmp/legal-rag-r3-phase61-final-embeddings.json.gz` checkpoint.
  `legal-rag-chunks-r3` contains 3,055 chunks (the 1,468 approved Delaware
  chunks plus the 1,587 staged SEC chunks). Production r2 remains unchanged
  at 1,468 chunks.
- Browser verification loaded the Microsoft/Activision official EX-2.1 URL
  and displayed the agreement. The SEC-compatible URL check subsequently
  passed for all 20 public sources with the declared `Data Org` contact
  identity.
- `gold-qa-v2-delaware-expansion` was attempted twice against r3 and received
  an Azure OpenAI HTTP 429 rate-limit response from `gpt-5-mini` both times;
  neither attempt produced a report. Do not promote r3. Resolve the sustained
  evaluation capacity constraint before another attempt.

## Evaluation pacing repair (pending live verification)

- The release evaluator now keeps `k=8` but uses an evaluation-only
  800-token completion cap and a 30-second delay between chat requests. It
  does not change the public application's 4,000-token answer setting.
- Chat completions now retry HTTP 429 responses using Azure's `retry-after`
  guidance. Run the r3 benchmark once after these changes are verified locally:

```bash
RETRIEVAL_BACKEND=azure_ai_search \
AZURE_SEARCH_ENDPOINT=https://srch-legal-rag-prod-278f1d.search.windows.net \
AZURE_SEARCH_INDEX_NAME=legal-rag-chunks-r3 \
AZURE_SEARCH_SOURCE_LOCATIONS_ENABLED=true \
uv run legal-rag-evaluate --gold data/evaluation/gold_qa_v2.json \
  --output /private/tmp/legal-rag-r3-phase61-evaluation.json
```

## Paced r3 evaluation result (2026-07-16)

- The paced benchmark completed without an Azure 429. It recorded 100%
  retrieval hit rate@8 (45/45) but only 28.9% citation-provenance validity
  (13/45). This fails the release evaluation gate; do not promote r3.
- The completion cap/pacing solved the infrastructure throttling but altered
  answer-generation behavior enough to invalidate the prior provenance metric.
  Investigate the missing citations before choosing a release-evaluation
  configuration or promoting the staged index.

## Do not do

- Do not promote r3, change the live app index, or publish SEC sources yet.
- Do not reuse `/private/tmp/legal-rag-r3-embeddings.json.gz` after chunk
  identities change.
- Do not solve the issue by truncating agreement text, inventing page numbers,
  or weakening the size gate.
