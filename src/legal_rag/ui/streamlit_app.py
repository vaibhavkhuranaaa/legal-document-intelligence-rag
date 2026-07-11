"""Streamlit demo UI for the Legal Document Intelligence platform.

Run with:  uv run streamlit run src/legal_rag/ui/streamlit_app.py
"""

import json

import streamlit as st

from legal_rag.rag.answer import AnswerService
from legal_rag.rag.azure_openai import AzureOpenAIClient
from legal_rag.rag.config import get_rag_settings
from legal_rag.rag.store import ChromaHybridStore

st.set_page_config(page_title="Legal Document Intelligence", page_icon="⚖️", layout="wide")

_EXAMPLE_QUESTIONS = [
    "What did the Delaware Supreme Court hold about deal price in the Dell appraisal?",
    "Why did the plaintiff in Abraham v. Wirtz fail to get a quasi-appraisal remedy?",
    "What price did VMware pay for Pivotal Software, and how did the court value the shares?",
    "What is the continuous holder requirement and how did it affect the Dell petitioners?",
]


@st.cache_resource
def _build_service() -> tuple[AnswerService, int]:
    settings = get_rag_settings()
    client = AzureOpenAIClient(settings)
    store = ChromaHybridStore(str(settings.chroma_persist_dir))
    return AnswerService(client, store), store.count()


@st.cache_resource
def _load_corpus() -> list[dict]:
    settings = get_rag_settings()
    if not settings.dataset_manifest_path.exists():
        return []
    manifest = json.loads(settings.dataset_manifest_path.read_text())
    return manifest.get("documents", [])


def _render_sidebar(chunk_count: int) -> None:
    st.sidebar.title("⚖️ Legal Document Intelligence")
    st.sidebar.caption(
        "Retrieval-augmented question answering over public Delaware M&A "
        "litigation, built on Azure Document Intelligence and Azure OpenAI. "
        "Every answer is grounded in retrieved passages with real citations."
    )
    st.sidebar.divider()
    st.sidebar.subheader("Corpus")
    for doc in _load_corpus():
        name = doc.get("display_name", doc.get("case_name", "?"))
        st.sidebar.markdown(f"**{name}**")
        st.sidebar.caption(f"{doc.get('court', '')} · {doc.get('docket_number', '')}")
    st.sidebar.divider()
    st.sidebar.caption(f"{chunk_count} indexed chunks · hybrid retrieval (vector + BM25)")
    st.sidebar.caption("Public documents only. Informational output — not legal advice.")


def main() -> None:
    try:
        service, chunk_count = _build_service()
    except Exception:
        st.error(
            "Could not initialize the answer service. Check that `.env` is "
            "configured and the index has been built (`legal-rag-index`)."
        )
        st.stop()

    _render_sidebar(chunk_count)

    st.title("Ask the corpus")

    example = st.selectbox(
        "Try an example question",
        ["(choose an example or type your own below)", *_EXAMPLE_QUESTIONS],
    )
    default = example if example in _EXAMPLE_QUESTIONS else ""
    question = st.text_area("Your question", value=default, height=80)

    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("Retrieving evidence and generating a grounded answer…"):
            answer = service.ask(question.strip())

        if answer.grounded:
            st.success("Grounded answer — every claim below cites retrieved passages.")
        else:
            st.warning(
                "The model could not fully ground this answer in the corpus. Treat it with caution."
            )
        st.markdown(answer.text)

        if answer.citations:
            st.divider()
            st.subheader("Sources")
            for citation in answer.citations:
                with st.expander(f"[{citation.marker}] {citation.display}"):
                    st.markdown(f"> {citation.snippet}")
                    st.caption(f"chunk `{citation.chunk_id}`")


main()
