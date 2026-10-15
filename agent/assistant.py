"""
Main assistant for Company Brain Agent.
Queries the MCP server (stdio subprocess or HTTP service) and synthesizes answers with citations.
"""

import ast
import json
import logging
import os
import re
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
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

# Tool definitions for Ollama native tool-calling.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search the knowledge base for relevant document chunks. Good for general 'what', 'who', 'when', and 'where' questions. For 'why' or rationale questions, use the `why` tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["policies", "product", "engineering", "meetings", "internal"],
                        "description": "Optional category to restrict the search. Omit if unsure."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read the full content of a document by its ID (e.g. 'policies/ai_deployment_policy'). Use this when you already know the exact document ID and need complete details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "Document ID, e.g. 'policies/ai_deployment_policy'."
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_policies",
            "description": "List all policy documents the current role can access.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_meeting_notes",
            "description": "Search meeting notes by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword or phrase to search for in meeting notes."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_categories",
            "description": "List all categories accessible to the current role.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "why",
            "description": "Explain the rationale, actors, and relationships around an entity or decision. REQUIRED when the user asks a 'why' question or asks for the reason behind a decision. Example entities: 'authentication decision', 'OAuth 2.0 implementation', 'Q4 2024'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "The entity or decision to explain, e.g. 'authentication decision', 'Q4 2024', 'AI deployment policy'."
                    }
                },
                "required": ["entity"]
            }
        }
    }
]

# Transport configuration
MCP_URL = os.getenv("COMPANY_BRAIN_MCP_URL")
API_KEY = os.getenv("COMPANY_BRAIN_API_KEY")
HTTP_TIMEOUT = 300.0


@dataclass
class AnswerResult:
    """Result of answering a question, including the answer text and tool-calling trace."""
    text: str
    steps: List[Dict[str, Any]]
    sources: List[Any]

    def __str__(self) -> str:
        return self.text


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
            cid = citation if isinstance(citation, str) else citation.get("id")
            if cid is None or any(c.get("id") == cid for c in citations):
                continue
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
        # Sometimes the model wraps arguments in backticks or extra text; try to find the dict.
        dict_match = re.search(r'\{.*?\}', input_str, re.DOTALL)
        if dict_match:
            input_str = dict_match.group(0)
        # LLMs may use Python literals (None, True/False, single quotes) instead of strict JSON.
        for parser in (ast.literal_eval, json.loads):
            try:
                args = parser(input_str)
            except (ValueError, SyntaxError, json.JSONDecodeError):
                continue
            if isinstance(args, dict):
                break
        else:
            logger.warning(f"Could not parse Action Input for {tool_name}: {input_str!r}")
            args = {}
        return tool_name, args

    async def answer_question(self, question: str) -> AnswerResult:
        """Answer a question using the LLM's native tool-calling capability."""
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
        steps: List[Dict[str, Any]] = []
        final_answer = ""
        tool_calls_made = 0

        # Route "why" / rationale questions straight to the knowledge graph tool.
        # This is more reliable for small models that otherwise default to search_documents.
        if re.match(r"\s*why\b", question, re.IGNORECASE):
            entity = re.sub(r"^\s*why\s+(?:did|was|is|are|do|does)\s+(?:we|you|they|it)\s*", "", question, flags=re.IGNORECASE).strip()
            entity = re.sub(r"^(?:did|was|is|are|do|does)\s+", "", entity, flags=re.IGNORECASE).strip()
            if not entity:
                entity = question
            result = await self.call_mcp_tool("why", {"entity": entity})
            steps.append({"tool": "why", "arguments": {"entity": entity}, "result": result, "error": result.get("error")})
            self._collect_doc_info(result, doc_dict, citations)
            tool_calls_made += 1
            messages.append({"role": "assistant", "content": f"I need to explain the rationale for '{entity}'."})
            messages.append({"role": "user", "content": f"Observation: {self._format_observation(result)}"})

        for i in range(MAX_TOOL_ITERATIONS):
            response = self.llm_client.chat(messages, tools=TOOLS)
            content = response.content.strip() if response.content else ""
            logger.debug(f"Agent response ({i}): content={content!r} tool_calls={len(response.tool_calls)}")

            if not response.tool_calls:
                if tool_calls_made > 0:
                    # The model is ready to answer.
                    final_answer = content
                    break
                # Force an initial search so the model has facts to work with.
                logger.warning("Model did not call a tool; forcing search_documents")
                result = await self.call_mcp_tool("search_documents", {"query": question})
                steps.append({"tool": "search_documents", "arguments": {"query": question}, "result": result, "error": result.get("error")})
                self._collect_doc_info(result, doc_dict, citations)
                tool_calls_made += 1
                messages.append({"role": "assistant", "content": "I need to search the knowledge base."})
                messages.append({"role": "user", "content": f"Observation: {self._format_observation(result)}"})
                continue

            # The model wants to call one or more tools.
            assistant_message: Dict[str, Any] = {"role": "assistant", "content": content, "tool_calls": []}
            tool_messages: List[Dict[str, Any]] = []
            for idx, tc in enumerate(response.tool_calls):
                tool_name = tc.name
                arguments = tc.arguments
                logger.info(f"Tool call: {tool_name}({arguments})")
                result = await self.call_mcp_tool(tool_name, arguments)
                steps.append({"tool": tool_name, "arguments": arguments, "result": result, "error": result.get("error")})
                self._collect_doc_info(result, doc_dict, citations)
                tool_calls_made += 1

                tool_call_id = tc.raw.get("id") or f"call_{i}_{idx}"
                assistant_message["tool_calls"].append({
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                })
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(result),
                })

            messages.append(assistant_message)
            messages.extend(tool_messages)

        if not final_answer:
            final_answer = "I couldn't find a clear answer in the company documents."

        # Append formatted sources for the user-facing answer
        if citations:
            final_answer += self.citation_formatter.format_citations(citations, doc_dict)

        # Store only the body (without the appended Sources block) in conversation history
        # to keep subsequent context compact. Citations are already stored separately.
        body = final_answer.split("\n\n**Sources:**\n")[0].strip()
        self.conversation_history.add_assistant_message(body, citations)

        return AnswerResult(text=final_answer, steps=steps, sources=citations)
    
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
                print(f"\nAnswer: {answer.text}")
        
        except EOFError:
            pass


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print("\nExiting...")
