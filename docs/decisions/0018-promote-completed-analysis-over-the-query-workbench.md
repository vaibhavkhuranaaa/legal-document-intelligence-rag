# ADR-0018: Promote completed analysis over the query workbench

## Decision

Render the full Filing Review Ledger only while a reviewer is framing a
question. After a successful search, replace that workbench with a compact
question-on-record rail and place the findings, citation-link coverage, and
source ledger in the first viewport. Move keyboard focus to the findings
heading without changing the scroll position.

Describe citation-link coverage as a literal count, such as `4 of 4 cited
records link to a public source`. Do not present that coverage as a score,
confidence measure, or legal-correctness judgment.

## Why

The prior result page retained the complete heading, search form, example
questions, and collection register above the answer. A completed analysis
began about 1,233 pixels down on desktop and 2,076 pixels down on mobile. That
made a successful request look unchanged and forced reviewers to search for
the new information.

The prior `SUPPORTED / 100` treatment also gave source-link availability the
visual form of a correctness or confidence score, even though the underlying
measure only checks whether displayed citations resolve to public sources.

## Alternatives rejected

- Automatically scrolling past the unchanged workbench was rejected because
  the stale question-entry state would still dominate the document order and
  screen-reader path.
- A dedicated persisted result route was rejected because the application does
  not store generated answers. Re-running generation from a shareable GET
  request would create uncontrolled model usage and misleading persistence.
- Browser-side search history was rejected because retaining legal questions
  on the device would conflict with the interface's public-question and
  confidential-information boundary.

## Not done

No model, prompt, retrieval contract, corpus record, citation resolver, source
action, or cloud resource changed. The result remains an informational research
aid and does not become a legal opinion or correctness claim.

## Changed

Successful searches now expose the findings heading at 321 pixels on desktop
and 342 pixels on mobile while keeping `scrollY` at zero. The heading receives
programmatic focus, the compact rail provides an explicit path to ask another
question, and citation coverage uses public-link counts.

The empty workspace keeps the established ledger identity. At 390 by 844
pixels, the primary search action is visible at 711 pixels. The page, primary
navigation, and result state have no measured horizontal overflow. All checked
navigation, form, source, and footer actions meet the 44-pixel touch target.

The question field also exposes a live character count, an adjacent warning
against confidential or privileged information, and a Ctrl or Command plus
Enter shortcut. Example actions use explicit same-page language, and the
collection label now says `CURRENT` rather than implying real-time updates.
