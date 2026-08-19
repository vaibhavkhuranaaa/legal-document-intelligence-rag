# ADR-0014: Separate deployment and runtime verification

## Decision

Build the App Service ZIP with `git archive` from the approved source revision.
Treat OneDeploy completion as the archive deployment result by disabling Azure
CLI runtime tracking. Stamp the revision, restart the app, and verify runtime
health in the existing post-deployment step.

## Why

The 2026-08-10 release uploaded successfully according to App Service, but the
Azure CLI continued tracking runtime startup and exited with an error about ten
minutes later. GitHub then skipped the revision stamp and live checks. The
workflow reported a failed upload even though OneDeploy had completed.

## Alternatives rejected

- Increasing the deployment timeout again was rejected because the upload had
  already succeeded. A longer wait would not correct the mixed deployment and
  runtime status contract.
- Matching a specific deployment log message was rejected because the earlier
  asynchronous workflow did not reliably observe that text.
- Building a custom deployment client was rejected because Azure CLI already
  exposes separate deployment and runtime tracking behavior.

## Not done

No Azure resource, corpus index, application behavior, retrieval logic,
citation behavior, or public claim changed. No deployment was triggered.

## Changed

The archive now contains only files tracked by the approved Git revision. The
upload step disables runtime status tracking, while the existing source stamp,
restart, health check, and route checks remain the release authority.
