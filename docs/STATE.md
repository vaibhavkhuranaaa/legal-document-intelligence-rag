# State

- Lifecycle: `maintained`
- Deployment: `live`
- Exposure: `anonymous`
- Production claim: `false`
- Publication: approved legacy v1 SHA; v2 replacement is in draft PR 1 and awaits exact-SHA preview and registry approval
- Public corpus: promoted `legal-rag-chunks-r3`, 3,055 chunks; r2 retained for rollback
- Evidence: release evaluation, source registry/disclosure, repository tests, and a 2026-07-23 root reachability check

The Azure App Service root returned HTTP 200 at `2026-07-23T20:57:44Z`. This is reachability evidence only. The anonymous research workspace is not a confidential legal-matter system and makes no production-SLO or legal-advice claim.

Migration verification: Ruff passed; `PYTHONPATH=src .venv/bin/python -m pytest -q` passed 178 tests. The ignored virtual environment still contains editable-install metadata and console-script paths from the repository's former `Development/Projects` location; recreate it separately rather than treating generated-path drift as a source failure. Run the publication and live profiles again after any manifest or evidence change.
