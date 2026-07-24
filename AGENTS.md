# Legal Document Intelligence RAG agent contract

## Authority

- Current implementation and release state: `docs/STATE.md`.
- Continuation instructions: `docs/HANDOFF.md`.
- Architecture, decisions, product scope, and deployment: `docs/architecture.md`, `docs/decisions.md`, `docs/product.md`, and `docs/deployment.md`.
- Public facts, evidence, disclosure, deployment classification, and résumé candidates: `portfolio/project.json`.
- Public corpus provenance and release evaluation: `data/dataset_manifest.json` and `data/evaluation/latest.json`.

## Working rules

- Query fresh `graphify-out/` context first when it covers the relevant files; otherwise inspect source directly.
- Use only registered public legal sources. Never introduce client, firm, confidential, privileged, or user-uploaded matter data.
- Do not promote retrieval, provenance, root reachability, or synthetic checks into legal accuracy, availability, confidentiality, security, or production-readiness claims.
- Preserve unrelated dirty and untracked work, including the existing local `.agents/`, `.claude/`, and `data/release-5a-input/` items.
- Use Python 3.12, `uv`, the `src/` layout, typed boundaries, and deterministic tests. Never install into system Python or hand-edit generated dependency outputs.
- Use purpose branches, conventional commits, and the configured human identity only; never add AI/model author or co-author attribution.
- Merging a completed release to `main` authorizes automatic redeployment to the declared existing Azure target, live-SHA verification, and portfolio synchronization. New or expanded paid capacity and data-release promotion remain owner-gated.
- Delegation is optional and must be bounded.

Run Ruff and the repository tests before handoff. Update state, handoff, architecture/ADR documentation, deployment evidence, and the manifest whenever their owning facts change.
