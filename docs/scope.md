# Scope

## In scope

- Read-only research over registered public Delaware court opinions and SEC transaction documents.
- Structure-aware retrieval from the promoted public corpus.
- Answers constrained to retrieved evidence, with numbered citations or an explicit refusal.
- Source review through canonical public URLs, document metadata, section paths, page ranges when the source is paginated, and evidence excerpts.
- Versioned retrieval and citation-provenance evaluation.
- Anonymous demonstration on the existing Azure App Service.

## Decision supported

The workspace helps a reviewer decide whether the registered public corpus contains retrievable, traceable evidence relevant to a focused research question. It does not decide the legal meaning, correctness, or weight of that evidence.

## Out of scope

- Legal advice, legal opinions, drafting, or attorney-reviewed answer correctness.
- Confidential, privileged, client, firm, or user-uploaded documents.
- Matter isolation, retention controls, malware scanning, discovery holds, or production service-level claims.
- Unregistered web sources or model knowledge presented as evidence.
- Automatic corpus promotion or infrastructure provisioning during application requests.

## Data boundary

The committed registry contains source metadata and integrity values for official public documents. Raw documents, extracted corpora, embeddings, local run state, credentials, and generated dependency graphs are not release artifacts in this repository.

## Release boundary

Application code can be released independently from the promoted retrieval index. Deployment must use an exact tracked revision, preserve the existing index, and verify the reported source revision plus the public research routes after restart.
