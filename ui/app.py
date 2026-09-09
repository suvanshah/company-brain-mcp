"""
Streamlit chat UI for Company Brain.

Streamlit re-runs this script on every interaction, but the assistant owns a
long-lived MCP server subprocess. So the assistant lives on a background thread
with its own event loop, created once per process via st.cache_resource, and
the UI submits questions to it.

Run from the project root:  streamlit run ui/app.py
"""

import asyncio
import os
import sys
import threading
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.assistant import CompanyBrainAssistant  # noqa: E402


class AssistantWorker:
    """Runs a CompanyBrainAssistant on a dedicated thread + event loop."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.assistant = CompanyBrainAssistant()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self._run(self.assistant.start_mcp_server())

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def ask(self, question: str) -> str:
        return self._run(self.assistant.answer_question(question))

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
    server_role = os.getenv("COMPANY_BRAIN_ROLE", "guest")
    st.markdown(f"**Server role:** `{server_role}`")
    st.markdown(f"**MCP server:** `{worker.assistant.mcp_client.server_info.name}` "
                f"v{worker.assistant.mcp_client.server_info.version}")
    if st.button("Clear conversation"):
        st.session_state.messages = []
        worker.clear()
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("Sources"):
                st.markdown(msg["sources"])

if question := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching documents and generating answer..."):
            answer = worker.ask(question)
        body, sources = split_sources(answer)
        st.markdown(body)
        if sources:
            with st.expander("Sources"):
                st.markdown(sources)

    st.session_state.messages.append({"role": "assistant", "content": body, "sources": sources})
