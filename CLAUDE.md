# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. It is the permanent operating manual for how to work here — not a project description.

## Overview

This repository contains a production-grade AI engineering portfolio project focused on M&A legal document intelligence, demonstrating production-quality software engineering using Azure AI services, modern Python tooling, evaluation, testing, documentation, CI/CD, and deployment.

Only public, reproducible legal datasets may be used. Never introduce confidential, proprietary, or client data into this repository.

Current project status, roadmap, architecture, technical decisions, and product scope are maintained in `docs/roadmap.md`, `docs/architecture.md`, `docs/decisions.md`, and `docs/product.md`. These documents are the source of truth for project planning — do not duplicate their content here.

## Repository Goals

- Build production-quality software.
- Demonstrate real AI engineering skills.
- Maintain an interview-ready repository at all times.
- Prefer maintainability, clarity, reproducibility, and correctness over clever implementations.
- Keep documentation synchronized with implementation.

## Development Workflow

Always work in clearly defined phases. For every phase:

1. Understand the objective.
2. Explain the proposed implementation and important architectural tradeoffs.
3. Wait for approval.
4. Implement only the approved scope.
5. Verify changes.
6. Summarize completed work.
7. Wait before beginning the next phase.

Never skip phases. Do not implement future phases early.

## Engineering Principles

- Build production-quality code; never fabricate functionality, evaluation metrics, benchmarks, deployment results, or invented Azure services/APIs/SDK behavior.
- Recommend best practices by default. Ask clarifying questions only when a decision has significant long-term architectural impact — avoid unnecessary implementation questions.
- Prefer readable, explicit code over clever or implicit behavior.
- Keep modules and functions small, focused, and cohesive; eliminate duplication whenever practical.
- Favor composition over unnecessary abstraction.

## Python Standards

- Python 3.12.
- Use `uv` for dependency and virtual environment management; `pyproject.toml` is the single source of truth. Never install packages into the system Python, and never recommend `pip` unless explicitly required.
- Use `src` layout.
- Prefer type hints where appropriate.

## Git Standards

- Follow Conventional Commits whenever appropriate.
- Never include AI co-author trailers (`Co-Authored-By: Claude...`) unless explicitly requested.
- Prefer small, logical commits. Never commit broken code.
- Before suggesting a commit, verify: Ruff passes, Pytest passes, documentation is updated, and no secrets are present.
- Never rewrite published Git history unless explicitly requested.

## Repository Structure

Keep the repository clean and organized around three primary folders: `src/`, `tests/`, `docs/`. Avoid creating additional top-level folders unless there is a strong architectural reason.

Documentation responsibilities:

- `architecture.md` → system architecture
- `roadmap.md` → implementation roadmap
- `decisions.md` → architectural decisions

## Technology Stack

Primary technologies: Python, Azure Document Intelligence, Azure OpenAI, LangChain, Chroma (development), Azure AI Search (future production option), Streamlit, Azure App Service.

Do not introduce additional frameworks or services without explaining why they improve the architecture.

## Security Standards

Treat security as a default requirement. Never hardcode secrets, commit credentials, commit `.env` files, commit downloaded datasets, commit generated vector databases, or commit large binary artifacts. Always use environment variables.

## Testing Standards

- Add or update tests when implementing new functionality.
- Keep tests deterministic and prefer fast unit tests.
- Explain integration testing requirements separately.

## Documentation Standards

Documentation should evolve alongside implementation. Whenever architecture changes: update `architecture.md`, record significant decisions in `decisions.md`, and update roadmap progress when milestones are completed. Never allow documentation to drift significantly from implementation.

## Communication Style

When proposing work: explain why, keep explanations concise, recommend the best engineering solution, explain important tradeoffs, avoid unnecessary implementation questions, and stop after each approved milestone.

Act as a senior software engineer collaborating on a production repository rather than as a conversational assistant.
