"""
Streamlit chat UI for Company Brain.

Streamlit re-runs this script on every interaction, but the assistant owns a
long-lived MCP server subprocess. So the assistant lives on a background thread
with its own event loop, created once per process via st.cache_resource, and
the UI submits questions to it.

Run from the project root:  streamlit run ui/app.py
"""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.assistant import AnswerResult, CompanyBrainAssistant  # noqa: E402
from server.config import OLLAMA_EMBEDDING_MODEL, OLLAMA_LLM_MODEL  # noqa: E402


class AssistantWorker:
    """Runs a CompanyBrainAssistant on a dedicated thread + event loop."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.assistant = CompanyBrainAssistant()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self._run(self.assistant.start_mcp_server())

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def ask(self, question: str) -> AnswerResult:
        return self._run(self.assistant.answer_question(question))

    def list_categories(self) -> dict:
        return self._run(self.assistant.call_mcp_tool("list_categories", {}))

    def clear(self):
        self.assistant.clear_history()


@st.cache_resource(show_spinner="Starting MCP server and indexing documents...")
def get_worker() -> AssistantWorker:
    return AssistantWorker()


def split_sources(answer: str) -> tuple[str, str | None]:
    """Separate the answer body from the appended **Sources:** block."""
    marker = "\n\n**Sources:**\n"
    if marker in answer:
        body, sources = answer.split(marker, 1)
        return body, sources
    return answer, None


st.set_page_config(page_title="Company Brain", page_icon=None, layout="centered")
st.title("Company Brain")
st.caption("Ask questions about company policies, product docs, engineering docs and meeting notes.")
st.caption(
    "Try asking:  \n"
    "What is our AI deployment policy?  \n"
    "What decisions were made about authentication?  \n"
    "What's on the product roadmap for Q4 2024?  \n"
    "What are our security requirements?"
)

worker = get_worker()

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Company Brain")
    server_role = os.getenv("COMPANY_BRAIN_ROLE", "guest")
    st.markdown(f"**Role:** `{server_role}`")
    st.markdown(f"**MCP server:** `{worker.assistant.mcp_client.server_info.name}` "
                f"v{worker.assistant.mcp_client.server_info.version}")

    st.divider()
    st.subheader("Models")
    st.markdown(f"**LLM:** `{OLLAMA_LLM_MODEL}`")
    st.markdown(f"**Embeddings:** `{OLLAMA_EMBEDDING_MODEL}`")

    st.divider()
    st.subheader("Knowledge base")
    try:
        cat_result = worker.list_categories()
        if cat_result.get("success"):
            for cat in cat_result["data"]:
                st.markdown(f"- `{cat['category']}`: {cat['document_count']} docs")
            total = sum(cat["document_count"] for cat in cat_result["data"])
            st.markdown(f"**Total:** {total} documents")
        else:
            st.caption(f"Categories unavailable: {cat_result.get('error')}")
    except Exception as e:
        st.caption(f"Stats unavailable: {e}")

    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        worker.clear()
        st.rerun()

def _step_query(tool: str, args: dict) -> str:
    """Convert tool arguments into a short, human-readable query string."""
    if tool == "search_documents":
        query = args.get("query", "")
        category = args.get("category")
        return f"'{query}'" + (f" in `{category}`" if category else " across all categories")
    if tool == "read_document":
        return f"`{args.get('doc_id', '')}`"
    if tool == "find_meeting_notes":
        return f"'{args.get('query', '')}'"
    if tool == "why":
        return f"'{args.get('entity', '')}'"
    if tool == "list_policies":
        return "list policies"
    if tool == "list_categories":
        return "list categories"
    return ""


def _render_graph_tree(triples: list):
    """Render triples as a subject-centered relationship tree, merging near-duplicate objects."""
    if not triples:
        st.caption("No matching facts found.")
        return

    by_subject: dict = {}
    for t in triples:
        subject = t.get("subject", "Unknown")
        predicate = t.get("predicate", "Unknown")
        obj = t.get("object", "")
        doc_id = t.get("doc_id", "Unknown")

        by_subject.setdefault(subject, {}).setdefault(predicate, {})
        key = obj.strip().lower().rstrip(".")
        if key not in by_subject[subject][predicate]:
            by_subject[subject][predicate][key] = {"object": obj.strip(), "sources": set()}
        by_subject[subject][predicate][key]["sources"].add(doc_id)

    for subject, predicates in by_subject.items():
        st.markdown(f"**{subject}**")
        for predicate, objects in predicates.items():
            for obj_data in objects.values():
                sources = " ".join(f"`{d}`" for d in sorted(obj_data["sources"]))
                st.markdown(
                    f"- **{predicate}** → *{obj_data['object']}*  <small>{sources}</small>",
                    unsafe_allow_html=True,
                )


def _render_step_data(tool: str, data: list | dict):
    """Render the data returned by a tool, focusing on the most relevant items."""
    if not data:
        st.caption("No matching data returned.")
        return

    if tool == "why":
        _render_graph_tree(data)
        return

    if tool == "search_documents":
        items = data[:3]
        st.markdown("**Top matching chunks:**")
        for item in items:
            title = item.get("title", "Unknown")
            section = item.get("section")
            snippet = item.get("snippet", "")
            header = f"{title} — {section}" if section else title
            st.markdown(f"- **{header}**: {snippet[:200]}")
        return

    if tool == "read_document":
        title = data.get("title", data.get("id", "Unknown"))
        content = data.get("content", "")[:400]
        st.markdown(f"**Read `{title}`**")
        st.caption(content + "..." if len(data.get("content", "")) > 400 else content)
        return

    if tool == "find_meeting_notes":
        items = data[:3]
        st.markdown("**Matching meeting notes:**")
        for item in items:
            title = item.get("title", "Unknown")
            snippet = item.get("snippet", "")[:200]
            st.markdown(f"- **{title}**: {snippet}")
        return

    if tool in ("list_policies", "list_categories"):
        st.markdown("**Results:**")
        for item in data[:10]:
            if isinstance(item, dict):
                name = item.get("title") or item.get("category") or item.get("id") or str(item)
                st.markdown(f"- {name}")
            else:
                st.markdown(f"- {item}")
        return

    # Fallback: show compact count
    st.caption(f"Returned {len(data) if isinstance(data, list) else 1} item(s).")


def _why_data_key(data: list) -> tuple:
    """Normalize a list of triples so duplicate why results can be detected."""
    return tuple(sorted(
        (t.get("subject", ""), t.get("predicate", ""), t.get("object", "").strip().lower())
        for t in data
    ))


def render_steps(steps: list):
    """Render a clean, human-readable retrieval trace."""
    if not steps:
        return
    with st.expander("How this was answered"):
        last_why_key = None
        for i, step in enumerate(steps, 1):
            tool = step["tool"]
            args = step.get("arguments", {})
            result = step.get("result", {})
            error = step.get("error")
            data = result.get("data") if isinstance(result, dict) and result.get("success") else None

            st.markdown(f"**{i}. {tool}** — queried {_step_query(tool, args)}")

            if error:
                st.caption(f"No useful data: {error}")
            elif not data:
                st.caption("No useful data returned.")
            elif tool == "why":
                key = _why_data_key(data)
                if key == last_why_key:
                    st.caption("Follow-up query confirmed the same graph facts.")
                else:
                    _render_graph_tree(data)
                    last_why_key = key
            else:
                _render_step_data(tool, data)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                st.markdown(msg["sources"])
        render_steps(msg.get("steps", []))

if question := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching documents and generating answer..."):
            answer = worker.ask(question)
        body, sources = split_sources(answer.text)
        st.markdown(body)
        if sources:
            with st.expander("Sources"):
                st.markdown(sources)
        render_steps(answer.steps)

    st.session_state.messages.append({"role": "assistant", "content": body, "sources": sources, "steps": answer.steps})
