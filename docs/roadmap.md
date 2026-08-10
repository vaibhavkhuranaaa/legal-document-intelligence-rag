# Roadmap

Work proceeds one phase at a time. Each phase must be explicitly approved before
the next begins.

## Phase 0 — Repository Bootstrap (current)

Status: **Complete, pending final approval**

- Project structure, dependency management (`uv`), linting (`ruff`), and test
  harness (`pytest`) in place.
- No application code, SDKs, or RAG logic yet.

## Future phases

Not yet planned in detail. Each future phase (data ingestion, document parsing via
Azure Document Intelligence, chunking/embedding, vector store, retrieval + Azure
OpenAI generation, Streamlit UI, Azure App Service deployment) will be scoped and
added here immediately before it is implemented, along with the tradeoffs
considered — not drafted in advance.
