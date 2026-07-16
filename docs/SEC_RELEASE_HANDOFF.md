# SEC corpus-release handoff

Last updated: 2026-07-16

## Current safe state

- The public Flask app remains on `legal-rag-chunks-r2` with 1,468 Delaware
  opinion chunks. Do not change its index setting during this work.
- `legal-rag-chunks-r3` is staged only and has no promoted content.
- Six official SEC EX-2.1 inputs are checksum-registered in
  `data/dataset_manifest.json` as `approved_pending_ingestion`. Their local
  source and processed artifacts are ignored and must never be committed.

## Verified release finding

The initial r3 rehearsal did not reveal a general Azure capacity problem. It
revealed malformed release payloads:

- Before repair, 3,137 chunks contained 288,443,966 embedding characters; the
  largest was 2,516,683 characters from Broadcom/VMware.
- Cause one: HTMLParser does not apply browser implied-end-tag rules. An
  unclosed EDGAR `<p>` capture absorbed later document content and became a
  false heading/path. This is repaired in `ingestion/sec_edgar.py`.
- After that repair, all six filings have ordinary raw paragraph bounds (the
  largest is 5,014 characters), but some genuine agreement paragraphs produce
  8,191–28,482-character embedding payloads. The chunker currently only
  groups paragraphs; it does not split a single paragraph.
- `rag/chunking.py` now blocks any embedding payload above 8,000 characters
  before it can call Azure OpenAI. This guard is intentional and must remain.

## Next bounded task: Phase 6.1

Implement provenance-preserving splitting for an individual oversized SEC
paragraph. Split at legal sentence/list boundaries where possible, never drop
or silently truncate text, retain the original section path and official HTML
anchor, and retain a truthful enclosing source span when a finer exact span is
not available. Add deterministic tests for long paragraphs, nested lists, and
the release gate.

Release acceptance criteria:

1. Every SEC chunk passes the 8,000-character embedding-payload gate.
2. All six records validate with their registered checksum and official URL.
3. A clean r3 rebuild uses a new checkpoint (the old 160-vector checkpoint is
   incompatible with repaired chunk identities).
4. Azure-backed evaluation and browser evidence-link checks pass before r3 is
   promoted.

## Do not do

- Do not promote r3, change the live app index, or publish SEC sources yet.
- Do not reuse `/private/tmp/legal-rag-r3-embeddings.json.gz` after chunk
  identities change.
- Do not solve the issue by truncating agreement text, inventing page numbers,
  or weakening the size gate.
