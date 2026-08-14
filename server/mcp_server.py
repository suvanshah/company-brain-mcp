"""
Main MCP Server for Company Brain.
Implements the Model Context Protocol server for document access.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from config import (
    MCP_SERVER_NAME, MCP_SERVER_VERSION, LOG_LEVEL, LOG_FILE
)
from document_loader import DocumentLoader
from permissions import PermissionManager, Role
from tools import MCPTools, ToolResult
from embeddings import EmbeddingSearch


# Setup logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server for Company Brain."""
    
    def __init__(self):
        self.loader = DocumentLoader()
        self.permission_manager = PermissionManager()
        self.embedding_search = EmbeddingSearch()
        self.tools = MCPTools(self.loader, self.permission_manager, self.embedding_search)
        self.current_role = Role.GUEST  # Default role
        
        # Load documents
        logger.info("Loading documents from knowledge base...")
        documents = self.loader.load_all()
        logger.info(f"Loaded {len(documents)} documents")
        
        # Index documents for semantic search
        logger.info("Indexing documents for semantic search...")
        self.embedding_search.index_documents(documents)
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an MCP request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        logger.info(f"Received request: {method}")
        
        try:
            if method == "initialize":
                return await self._handle_initialize(params, request_id)
            elif method == "tools/list":
                return await self._handle_tools_list(request_id)
            elif method == "tools/call":
                return await self._handle_tool_call(params, request_id)
            elif method == "set_role":
                return await self._handle_set_role(params, request_id)
            else:
                return self._error_response(request_id, -32601, "Method not found")
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return self._error_response(request_id, -32603, str(e))
    
    async def _handle_initialize(self, params: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION
                },
                "capabilities": {
                    "tools": {}
                }
            }
        }
    
    async def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = [
            {
                "name": "list_policies",
                "description": "List all policy documents",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "read_document",
                "description": "Read a specific document by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document ID to read"
                        }
                    },
                    "required": ["doc_id"]
                }
            },
            {
                "name": "search_documents",
                "description": "Search documents by query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category to search within"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "find_meeting_notes",
                "description": "Find meeting notes matching a query",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for meeting notes"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "list_categories",
                "description": "List all accessible categories",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": tools}
        }
    
    async def _handle_tool_call(self, params: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Tool call: {tool_name} with args: {arguments}")
        
        # Get current role from arguments or use default
        role_str = arguments.pop("role", "guest")
        role = self.permission_manager.role_from_string(role_str)
        
        # Call the appropriate tool
        if tool_name == "list_policies":
            result = self.tools.list_policies(role)
        elif tool_name == "read_document":
            result = self.tools.read_document(arguments.get("doc_id"), role)
        elif tool_name == "search_documents":
            result = self.tools.search_documents(
                arguments.get("query"),
                role,
                arguments.get("category")
            )
        elif tool_name == "find_meeting_notes":
            result = self.tools.find_meeting_notes(arguments.get("query"), role)
        elif tool_name == "list_categories":
            result = self.tools.list_categories(role)
        else:
            return self._error_response(request_id, -32601, f"Unknown tool: {tool_name}")
        
        if result.success:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result.data, indent=2)
                        }
                    ],
                    "citations": result.citations or []
                }
            }
        else:
            return self._error_response(request_id, -32602, result.error)
    
    async def _handle_set_role(self, params: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle set_role request (custom extension)."""
        role_str = params.get("role", "guest")
        self.current_role = self.permission_manager.role_from_string(role_str)
        
        logger.info(f"Role set to: {self.current_role}")
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "role": self.current_role.value,
                "accessible_categories": list(self.permission_manager.get_accessible_categories(self.current_role))
            }
        }
    
    def _error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    async def run(self):
        """Run the MCP server (stdio transport)."""
        logger.info("Starting MCP server...")
        
        while True:
            try:
                # Read line from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, input
                )
                
                if not line.strip():
                    continue
                
                request = json.loads(line)
                response = await self.handle_request(request)
                print(json.dumps(response))
                print()  # MCP requires blank line after response
                
            except EOFError:
                logger.info("Client disconnected")
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                logger.error(f"Server error: {e}")


async def main():
    """Main entry point."""
    server = MCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
