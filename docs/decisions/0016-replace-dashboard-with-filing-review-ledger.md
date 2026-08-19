# ADR-0016: Replace the dashboard with a filing review ledger

## Decision

Replace the generic dashboard treatment with a professional filing-review workspace. Use an asymmetric research desk, collection register, findings docket, source-match register, evidence ledger, source register, release register, and methodology register. Preserve the existing source-citation behavior and evidence boundaries.

## Why

Legal research is a document-review task, not a KPI-monitoring task. The new visual system makes the question, finding, source coordinate, retrieved passage, and canonical public record part of one review flow. Registry blue communicates selection and navigation. Signal red is reserved for errors or incomplete support. Retrieval relevance remains explicitly separate from legal correctness.

## Alternatives rejected

- A conventional card dashboard was rejected because repeated metric tiles obscure the primary research decision.
- A dark investigative interface was rejected because it made long-form evidence review less readable and felt theatrical for the public-source corpus.
- A publication-style type specimen was rejected because expressive typography competed with source coordinates and operational controls.
- Hiding limitations in secondary documentation was rejected because reviewers need the legal-information boundary beside the evidence.

## Not done

No answer-generation logic, citation resolver, source registry, benchmark result, legal limitation, corpus, or cloud resource changed. No visual framework, font package, or runtime dependency was added.

## Changed

The interface now uses cool paper, carbon ink, registry blue, signal red, ruled ledgers, square controls, tabular figures, and responsive vertical records. Loading, empty, error, and answer states share the same evidence-first hierarchy. Browser checks at 1440px and 390px show no horizontal page overflow, and primary mobile targets are at least 44 pixels high.
