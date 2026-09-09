"""
Main assistant for Company Brain Agent.
Queries the MCP server (stdio subprocess or HTTP service) and synthesizes answers with citations.
"""

import json
import logging
import os
import re
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import anyio
from mcp import Client
from mcp.client.stdio import StdioServerParameters

try:
    from mcp.client.streamable_http import streamable_http_client
    import httpx2
except ImportError:
    streamable_http_client = None  # type: ignore
    httpx2 = None  # type: ignore

from agent.ollama_client import OllamaClient
from agent.citation_formatter import CitationFormatter
from agent.prompt_templates import AGENT_SYSTEM_PROMPT
from agent.conversation_history import ConversationHistory

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = PROJECT_ROOT / "server" / "mcp_server.py"
MAX_TOOL_ITERATIONS = 5

# Transport configuration
MCP_URL = os.getenv("COMPANY_BRAIN_MCP_URL")
API_KEY = os.getenv("COMPANY_BRAIN_API_KEY")
HTTP_TIMEOUT = 300.0


class CompanyBrainAssistant:
    """Main assistant for answering questions about company documents."""
    
    def __init__(self):
        self.llm_client = OllamaClient()
        self.conversation_history = ConversationHistory()
        self.citation_formatter = CitationFormatter()
        self._stack: AsyncExitStack | None = None
        self.mcp_client: Client | None = None
    
    async def start_mcp_server(self):
        """Connect to the MCP server over stdio or HTTP and complete the handshake."""
        self._stack = AsyncExitStack()

        if MCP_URL:
            if streamable_http_client is None:
                raise RuntimeError("HTTP transport is not available; install httpx2/mcp client extras")
            logger.info(f"Connecting to MCP server over HTTP: {MCP_URL}")
            headers = {}
            if API_KEY:
                headers["Authorization"] = f"Bearer {API_KEY}"
                headers["X-API-Key"] = API_KEY
            http_client = httpx2.AsyncClient(
                headers=headers,
                timeout=httpx2.Timeout(30.0, read=HTTP_TIMEOUT),
                follow_redirects=True,
            )
            await self._stack.enter_async_context(http_client)
            transport = streamable_http_client(MCP_URL, http_client=http_client)
            self.mcp_client = await self._stack.enter_async_context(Client(transport))
        else:
            logger.info("Starting MCP server as subprocess over stdio...")
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER_SCRIPT)],
                cwd=str(PROJECT_ROOT),
                env=os.environ.copy(),
            )
            self.mcp_client = await self._stack.enter_async_context(Client(params))

        info = self.mcp_client.server_info
        logger.info(f"Connected to MCP server {info.name} v{info.version}")

    async def stop_mcp_server(self):
        """Disconnect from the MCP server / stop the subprocess."""
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self.mcp_client = None
            logger.info("MCP server stopped")
    
    async def __aenter__(self):
        await self.start_mcp_server()
        return self
    
    async def __aexit__(self, *exc):
        await self.stop_mcp_server()
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Call an MCP tool over the stdio transport."""
        if not self.mcp_client:
            await self.start_mcp_server()
        
        result = await self.mcp_client.call_tool(tool_name, arguments)
        
        if result.is_error:
            text = result.content[0].text if result.content else "Unknown error"
            return {"success": False, "data": None, "citations": [], "error": text}
        
        return json.loads(result.content[0].text)

    def _collect_doc_info(self, result: Dict, doc_dict: Dict[str, Dict], citations: List[Any]):
        """Extract document info and citations from a tool result."""
        if not result.get("success"):
            return

        data = result.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "id" in item:
                    doc_dict[item["id"]] = item
        elif isinstance(data, dict) and "id" in data:
            doc_dict[data["id"]] = data

        for citation in result.get("citations", []):
            if citation not in citations:
                if isinstance(citation, str):
                    citations.append({"id": citation})
                else:
                    citations.append(citation)

    @staticmethod
    def _extract_final_answer(content: str) -> Optional[str]:
        """Extract the Final Answer section from a ReAct response."""
        m = re.search(r'Final Answer:\s*(.*?)(?=\n(?:Thought|Action):|\Z)', content, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    @staticmethod
    def _format_observation(result: Dict) -> str:
        """Format a tool result as a concise observation for the LLM."""
        if not result.get("success"):
            return f"Observation: Error: {result.get('error', 'unknown error')}"

        data = result.get("data")
        if data is None:
            return "Observation: No results found."

        parts = ["Observation:"]
        if isinstance(data, list):
            for i, item in enumerate(data, 1):
                if isinstance(item, dict):
                    title = item.get("title") or item.get("id", f"result {i}")
                    section = item.get("section")
                    text = item.get("content") or item.get("snippet") or str(item)
                    header = f"{title} — {section}" if section else title
                    parts.append(f"[{i}] {header}:\n{text}")
                else:
                    parts.append(f"[{i}] {item}")
        elif isinstance(data, dict):
            title = data.get("title") or data.get("id", "result")
            text = data.get("content") or data.get("snippet") or str(data)
            parts.append(f"{title}:\n{text}")
        else:
            parts.append(str(data))

        return "\n\n".join(parts)

    @staticmethod
    def _parse_action(content: str) -> Optional[Tuple[str, Dict]]:
        """Parse the first Action / Action Input pair from a ReAct response."""
        action_match = re.search(r'Action:\s*(\w+)', content, re.IGNORECASE)
        if not action_match:
            return None
        tool_name = action_match.group(1).strip()

        input_match = re.search(
            r'Action Input:\s*(.*?)(?=\n(?:Thought|Action|Final Answer|Observation):|\Z)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        input_str = input_match.group(1).strip() if input_match else "{}"
        # Sometimes the model wraps arguments in backticks or extra text; try to find JSON.
        json_match = re.search(r'\{.*?\}', input_str, re.DOTALL)
        if json_match:
            input_str = json_match.group(0)
        try:
            args = json.loads(input_str)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse Action Input for {tool_name}: {input_str!r}")
            args = {}
        return tool_name, args

    async def answer_question(self, question: str) -> str:
        """Answer a question using a ReAct-style agent loop."""
        logger.info(f"Answering question: {question}")

        if not self.mcp_client:
            await self.start_mcp_server()

        self.conversation_history.add_user_message(question)

        # Build the message list for this turn:
        # system prompt first, then the stored conversation history (including the current question).
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        messages.extend(self.conversation_history.get_context_for_llm())

        doc_dict: Dict[str, Dict] = {}
        citations: List[Any] = []
        final_answer = ""
        tool_calls_made = 0

        for i in range(MAX_TOOL_ITERATIONS):
            response = self.llm_client.chat(messages)
            content = response.content.strip() if response.content else ""
            logger.debug(f"Agent response ({i}): {content[:500]}")

            final = self._extract_final_answer(content)
            if final and tool_calls_made > 0:
                final_answer = final
                break
            elif final:
                # Model tried to answer before using any tools; ignore and force a search.
                logger.warning("Model gave Final Answer before using tools; forcing search")

            action = self._parse_action(content)
            if not action:
                if tool_calls_made == 0:
                    # Force an initial search so the model has facts to work with.
                    logger.warning("Model did not use a tool; forcing search_documents")
                    action = ("search_documents", {"query": question})
                else:
                    # No further action and no final answer: use the raw content as the answer.
                    final_answer = content
                    break

            tool_name, arguments = action
            logger.info(f"Tool call: {tool_name}({arguments})")
            result = await self.call_mcp_tool(tool_name, arguments)
            self._collect_doc_info(result, doc_dict, citations)
            tool_calls_made += 1

            # Append the assistant's reasoning and a clean observation to continue the loop.
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": self._format_observation(result)})

        if not final_answer:
            final_answer = "I couldn't find a clear answer in the company documents."

        # Append formatted sources for the user-facing answer
        if citations:
            final_answer += self.citation_formatter.format_citations(citations, doc_dict)

        # Store only the body (without the appended Sources block) in conversation history
        # to keep subsequent context compact. Citations are already stored separately.
        body = final_answer.split("\n\n**Sources:**\n")[0].strip()
        self.conversation_history.add_assistant_message(body, citations)

        return final_answer
    
    def get_last_citations(self) -> List[Any]:
        """Return the citations from the most recent assistant turn."""
        for turn in reversed(self.conversation_history.turns):
            if turn.role == "assistant":
                return turn.citations
        return []

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")


async def main():
    """Main entry point for testing the assistant."""
    async with CompanyBrainAssistant() as assistant:
        print("Company Brain Assistant")
        print("Type 'quit' to exit, 'clear' to clear history")
        print("-" * 50)
        
        try:
            while True:
                question = (await anyio.to_thread.run_sync(
                    input, "\nYour question: ", abandon_on_cancel=True
                )).strip()
                
                if question.lower() == 'quit':
                    break
                elif question.lower() == 'clear':
                    assistant.clear_history()
                    print("History cleared")
                    continue
                elif not question:
                    continue
                
                answer = await assistant.answer_question(question)
                print(f"\nAnswer: {answer}")
        
        except EOFError:
            pass


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print("\nExiting...")
