# Architectural Decisions (ADR-lite)

Lightweight record of significant technical decisions and the tradeoffs behind
them. Each entry: context, decision, alternatives considered, consequences.

---

## ADR-0001: Dependency and environment management via `uv`

**Context:** Need reproducible, isolated Python environments without touching
system Python, and a single source of truth for dependencies.

**Decision:** Use `uv` for virtual environment creation and dependency
resolution/locking, driven entirely by `pyproject.toml` (+ generated `uv.lock`).
No `requirements.txt` as a primary artifact.

**Alternatives considered:** `pip` + `venv` + `requirements.txt` (slower,
no lockfile by default, more manual); `poetry` (viable, but `uv` is faster and
has become the standard for new projects).

**Consequences:** Contributors must have `uv` installed. A `requirements.txt`
can be generated on demand for deployment targets that require it
(`uv export`), but it is never hand-maintained.

---

## ADR-0002: `src` layout with package name `legal_rag`

**Context:** Need an import layout that prevents accidentally importing from
the working directory instead of the installed package, standard for
production-quality Python packages.

**Decision:** Use `src/legal_rag/` layout, installed in editable mode.

**Consequences:** Tests and tooling must run against the installed package
(via `uv run`), not via ad hoc `PYTHONPATH` manipulation.

---

## ADR-0003: Defer `mypy` until the codebase has enough surface area

**Context:** Static typing is valuable but adds friction disproportionate to a
near-empty codebase.

**Decision:** Configure only `ruff` (lint) and `pytest` (tests) in Phase 0.
Introduce `mypy` in a later phase once there are real modules and interfaces
worth type-checking.

**Consequences:** Type errors will not be caught until `mypy` is introduced;
acceptable given the current scope.
