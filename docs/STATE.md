# State

- Lifecycle: `maintained`
- Deployment: `live`
- Exposure: `anonymous`
- Production claim: `false`
- Publication: approved at exact public source commit `feeefeba500881f6624edf984340f618b2b41bb8`
- Public corpus: promoted `legal-rag-chunks-r3`, 3,055 chunks; r2 retained for rollback
- Evidence: release evaluation, source registry/disclosure, repository tests, and a 2026-07-23 root reachability check

The Azure App Service root returned HTTP 200 at `2026-07-23T20:57:44Z`. This is reachability evidence only. The anonymous research workspace is not a confidential legal-matter system and makes no production-SLO or legal-advice claim.

After explicit owner approval on 2026-07-23, GitHub visibility was changed to public. Anonymous checks returned HTTP 200 for the repository, exact source commit, and provider URL. The portfolio site, Resume Creator, and public GitHub index were synchronized from the same approved exact-SHA catalog.

Migration verification: Ruff passed; `PYTHONPATH=src .venv/bin/python -m pytest -q` passed 178 tests. The ignored virtual environment still contains editable-install metadata and console-script paths from the repository's former `Development/Projects` location; recreate it separately rather than treating generated-path drift as a source failure. Run the publication and live profiles again after any manifest or evidence change.
