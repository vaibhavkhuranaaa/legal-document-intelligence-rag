# ADR-0019: Publish by replacing remote main

## Decision

Publish the reviewed workspace by replacing remote `main` with the approved
revision under a recorded force-with-lease, rather than merging the development
history forward. Let the existing deployment workflow run from that revision,
then verify the live source stamp before touching repository metadata.

## Why

The development history carried the shape of the work rather than the shape of
the result: release attempts, reverted deployment experiments, and commits whose
messages describe problems that no longer exist. A reader arriving at a public
repository reads the history as documentation. Replacing it published one
reviewed state and kept the exact revision verifiable end to end, from the
repository through the running application to the portfolio page.

The lease made the replacement safe to record. Remote `main` was re-read
immediately before the push, so the operation would refuse if anything had
moved underneath it.

## Alternatives rejected

- Merging the branch forward was rejected because it publishes the deployment
  troubleshooting as though it were part of the finished design.
- An interactive rebase to curate the history was rejected because the result is
  still a history nobody will read, at a much higher chance of losing the exact
  revision the deployment and the portfolio both pin.
- Publishing a fresh repository was rejected because it discards the issue and
  workflow history that is genuinely useful, and it breaks existing links.

## Not done

No Azure resource, corpus index, retrieval behavior, citation behavior, or
public claim changed. The revision published is the revision reviewed.

## Changed

Remote `main` now holds one reviewed revision rather than the development
history. The deployment workflow runs from that revision, the application
stamps it, and the health endpoint reports it, so the published revision is
checkable from outside the project. Repository description, homepage, and
topics were applied after the live revision was verified, not before.

## Consequence found later

Replacing published history is not a one-time operation once it has been done
once. On 2026-08-19, after this milestone closed, remote `main` was replaced
again with a single squashed publication commit. That second replacement was
outside the recorded approval, and it silently dropped thirty lines from
`.gitignore`, including every rule excluding agent tooling and delivery state
from the public repository. Nothing had been committed through the gap, but the
guard was gone.

The lesson is not that the decision was wrong. It is that a repository which
accepts history replacement needs the protections that survive it: branch
protection on `main`, and a check that fails when the ignore rules regress. Both
are open items rather than claims.
