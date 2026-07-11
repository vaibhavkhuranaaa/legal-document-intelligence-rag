"""Grounded question answering over the retrieval store.

Grounding rules (product.md AI Principles, architecture review §7):
- The model answers ONLY from retrieved evidence, citing numbered markers.
- The model never composes citations from memory — it cites [n] markers,
  and this module resolves them to real document/section/page citations.
- If the evidence is insufficient, the model must say so; the answer is
  flagged `grounded=False` when no citation marker appears in it.
"""

import re

from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.models import Answer, Citation, ScoredChunk
from legal_rag.rag.store import RetrievalBackend

_SYSTEM_PROMPT = """\
You are a legal research assistant answering questions about a corpus of \
public court opinions and legal documents. You must follow these rules \
without exception:

1. Answer ONLY from the numbered context passages provided. Never use \
outside knowledge, even if you are confident.
2. Cite every factual statement with its passage marker, e.g. [1] or [2][3].
3. Quote key legal language exactly where it matters.
4. If the passages do not contain enough information to answer, say exactly: \
"The provided documents do not contain enough information to answer this \
question." and briefly note what related information IS present.
5. This is legal information from public documents, not legal advice.
"""

_MARKER_PATTERN = re.compile(r"\[(\d+)\]")

_NO_EVIDENCE_TEXT = "The provided documents do not contain enough information"


class AnswerService:
    def __init__(self, client: AzureOpenAIClient, store: RetrievalBackend) -> None:
        self._client = client
        self._store = store

    def ask(self, question: str, *, k: int = 8) -> Answer:
        query_vector = self._client.embed([question])[0]
        results = self._store.search(query_text=question, query_vector=query_vector, k=k)

        if not results:
            return Answer(
                question=question,
                text="The index is empty — no documents have been indexed yet.",
                citations=[],
                grounded=False,
            )

        context = self._build_context(results)
        user_prompt = f"Context passages:\n\n{context}\n\nQuestion: {question}"
        raw_answer = self._client.complete(system=_SYSTEM_PROMPT, user=user_prompt)

        cited_markers = self._extract_markers(raw_answer, limit=len(results))
        citations = [
            self._citation(marker, results[marker - 1]) for marker in sorted(cited_markers)
        ]
        grounded = bool(citations) and _NO_EVIDENCE_TEXT not in raw_answer

        return Answer(question=question, text=raw_answer, citations=citations, grounded=grounded)

    @staticmethod
    def _build_context(results: list[ScoredChunk]) -> str:
        blocks = []
        for i, scored in enumerate(results, start=1):
            c = scored.chunk
            section = " › ".join(c.section_path) if c.section_path else "(document body)"
            header = f"[{i}] {c.document_title} — {section} (pages {c.page_start}–{c.page_end})"
            blocks.append(f"{header}\n{c.text}")
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _extract_markers(text: str, *, limit: int) -> set[int]:
        return {int(m) for m in _MARKER_PATTERN.findall(text) if 1 <= int(m) <= limit}

    @staticmethod
    def _citation(marker: int, scored: ScoredChunk) -> Citation:
        c = scored.chunk
        snippet = c.text[:280] + ("…" if len(c.text) > 280 else "")
        return Citation(
            marker=marker,
            document_title=c.document_title,
            section_path=c.section_path,
            page_start=c.page_start,
            page_end=c.page_end,
            chunk_id=c.chunk_id,
            snippet=snippet,
        )
