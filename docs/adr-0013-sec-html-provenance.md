# ADR-0013: SEC HTML publication requires an honest section locator

**Status:** Accepted — Phase 5B implementation in progress

## Context

The Phase 5B parser and polite SEC client successfully processed six official
EX-2.1 merger agreements. The sampled EDGAR HTML has no stable DOM `id` or
`name` fragments associated with its substantive headings. Appending a
generated `#fragment` would create a link that appears precise but does not
resolve in the canonical SEC document.

## Decision

Treat SEC HTML as a distinct source kind. It carries the official filing URL,
CIK, accession number, form, filing date, exhibit identity, checksum, and a
heading/span locator. It never carries a PDF page claim. The release remains
blocked until the parser can preserve a truthful, reviewer-usable locator for
these documents without fabricating a URL fragment.

## Consequences

Court PDF citations remain unchanged. The public Corpus and Evidence views can
render `sec_html` sources only after their release validation proves the
official link and locator. This deliberately favors a broader official source
link over a false deep link.
