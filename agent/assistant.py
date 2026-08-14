"""
Main assistant for Company Brain Agent.
Queries MCP server and synthesizes answers with citations.
"""

import json
import logging
from typing import List, Dict, Optional
import subprocess
import asyncio

from ollama_client import OllamaClient
from citation_formatter import CitationFormatter
from prompt_templates import SYSTEM_PROMPT, RAG_PROMPT, POLICY_QUERY_PROMPT, MEETING_QUERY_PROMPT
from conversation_history import ConversationHistory

logger = logging.getLogger(__name__)


class CompanyBrainAssistant:
    """Main assistant for answering questions about company documents."""
    
    def __init__(self, role: str = "guest"):
        self.role = role
        self.llm_client = OllamaClient()
        self.conversation_history = ConversationHistory()
        self.citation_formatter = CitationFormatter()
        self.server_process = None
    
    async def start_mcp_server(self):
        """Start the MCP server as a subprocess."""
        logger.info("Starting MCP server...")
        self.server_process = subprocess.Popen(
            ["python", "server/mcp_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # Give server time to start
        await asyncio.sleep(2)
        logger.info("MCP server started")
    
    def stop_mcp_server(self):
        """Stop the MCP server."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process.wait()
            logger.info("MCP server stopped")
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Call an MCP tool."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        # For now, we'll use a simpler approach: direct Python imports
        # In production, this would use stdio MCP protocol
        from server.document_loader import DocumentLoader
        from server.permissions import PermissionManager, Role
        from server.tools import MCPTools
        from server.embeddings import EmbeddingSearch
        
        loader = DocumentLoader()
        loader.load_all()
        permission_manager = PermissionManager()
        embedding_search = EmbeddingSearch()
        embedding_search.index_documents(list(loader.documents.values()))
        tools = MCPTools(loader, permission_manager, embedding_search)
        
        role_enum = permission_manager.role_from_string(self.role)
        
        if tool_name == "search_documents":
            result = tools.search_documents(
                arguments.get("query"),
                role_enum,
                arguments.get("category")
            )
        elif tool_name == "read_document":
            result = tools.read_document(arguments.get("doc_id"), role_enum)
        elif tool_name == "list_policies":
            result = tools.list_policies(role_enum)
        elif tool_name == "find_meeting_notes":
            result = tools.find_meeting_notes(arguments.get("query"), role_enum)
        elif tool_name == "list_categories":
            result = tools.list_categories(role_enum)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        return {
            "success": result.success,
            "data": result.data,
            "citations": result.citations,
            "error": result.error
        }
    
    async def answer_question(self, question: str) -> str:
        """Answer a question using the knowledge base."""
        logger.info(f"Answering question: {question}")
        
        # Add user message to history
        self.conversation_history.add_user_message(question)
        
        # Search for relevant documents
        search_result = await self.call_mcp_tool("search_documents", {"query": question})
        
        if not search_result["success"]:
            error_msg = f"Error searching documents: {search_result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return error_msg
        
        documents = search_result["data"]
        citations = search_result["citations"]
        
        if not documents:
            no_info_msg = "I couldn't find any relevant information in the company documents to answer your question."
            self.conversation_history.add_assistant_message(no_info_msg, [])
            return no_info_msg
        
        # Build context from documents
        context = self._build_context(documents)
        
        # Choose appropriate prompt template
        if "policy" in question.lower():
            prompt = POLICY_QUERY_PROMPT.format(context=context, question=question)
        elif "meeting" in question.lower():
            prompt = MEETING_QUERY_PROMPT.format(context=context, question=question)
        else:
            prompt = RAG_PROMPT.format(context=context, question=question)
        
        # Generate answer using LLM
        answer = self.llm_client.generate(prompt, SYSTEM_PROMPT)
        
        # Add citations to answer
        if citations:
            doc_dict = {doc["id"]: doc for doc in documents}
            citations_text = self.citation_formatter.format_citations(citations, doc_dict)
            answer += citations_text
        
        # Add assistant message to history
        self.conversation_history.add_assistant_message(answer, citations)
        
        return answer
    
    def _build_context(self, documents: List[Dict]) -> str:
        """Build context string from documents."""
        context_parts = []
        for doc in documents:
            context_parts.append(f"Document: {doc['title']}")
            context_parts.append(f"Category: {doc['category']}")
            context_parts.append(f"Content: {doc['snippet']}")
            context_parts.append("---")
        return "\n".join(context_parts)
    
    def set_role(self, role: str):
        """Set the user role for access control."""
        self.role = role
        logger.info(f"Role set to: {role}")
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")


async def main():
    """Main entry point for testing the assistant."""
    import sys
    
    assistant = CompanyBrainAssistant(role="admin")
    
    print("Company Brain Assistant")
    print("Type 'quit' to exit, 'clear' to clear history")
    print("-" * 50)
    
    try:
        while True:
            question = input("\nYour question: ").strip()
            
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
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        assistant.stop_mcp_server()


if __name__ == "__main__":
    asyncio.run(main())
