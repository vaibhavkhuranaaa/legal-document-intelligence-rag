# ADR-0017: Use Serverless Search for the low-volume public demo

## Decision

Run the promoted `legal-rag-chunks-r3` index on Azure AI Search Serverless
Developer in West Central US. Keep Azure OpenAI generation usage-based and keep
the existing B1 App Service unchanged. Delete the prior Basic Search service
only after document, retrieval, live evidence, and answer-citation checks pass.

## Why

The public demo has infrequent, bursty research traffic. A dedicated Basic
Search unit created about $73.73 of fixed monthly cost even when the demo was
idle. Serverless Search can scale compute to zero and charges by compute use and
indexed storage after preview billing begins. This preserves managed identity,
hybrid retrieval, and the existing evidence boundary without operating a model
or search cluster continuously.

## Alternatives rejected

- Self-hosting an open source model and vector database was rejected because a
  continuously available host would replace a fixed managed-service charge
  with server operations, monitoring, and another fixed compute floor.
- Keeping Basic Search and limiting only model calls was rejected because model
  calls were already usage-based; the dedicated Search unit was the dominant
  fixed cost.
- Replacing the managed retrieval adapter was rejected because Serverless uses
  the existing query and citation path without an application code change.

## Not done

No model, prompt, answer policy, citation resolver, corpus document, retrieval
schema, App Service plan, public visibility, or confidential-data boundary was
changed. The local release candidate was not published as part of this
infrastructure migration.

## Changed

The 3,055 active documents were copied to `srch-legal-rag-sls-278f1d` and
verified for exact non-vector metadata parity. The same hybrid probe returned
the same top chunk. The live Evidence response was byte-identical on Basic and
Serverless, and a live generated answer retained seven source anchors. The app
endpoint then moved to Serverless and the Basic service was deleted.

Serverless Developer is a preview with no service-level agreement and is not
recommended by Microsoft for production workloads. Preview billing is
currently deferred, but Microsoft states it will provide at least 30 days
notice before billing begins. Future compute and indexed-storage charges must
be monitored. There is no retained r2 rollback index; recovery requires a
controlled rebuild from approved corpus artifacts.
