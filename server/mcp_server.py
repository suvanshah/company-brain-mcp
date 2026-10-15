"""
Main MCP Server for Company Brain.
Implements the Model Context Protocol server for document access.

Runs as its own process and speaks MCP (JSON-RPC over stdio) via the official
`mcp` SDK. stdout is the protocol channel, so all logging goes to stderr/file.

Run from the project root:
    python server/mcp_server.py
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server import MCPServer

# The connectors package lives at the project root, not inside server/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from connectors import SyncManager, FilesystemConnector  # noqa: E402

from config import (
    MCP_SERVER_NAME, MCP_SERVER_VERSION, SERVER_ROLE, LOG_LEVEL, LOG_FILE,
    KNOWLEDGE_DIR, CONNECTORS_JSON, BASE_DIR
)
from document_loader import DocumentLoader
from permissions import PermissionManager
from tools import MCPTools, ToolResult
from embeddings import EmbeddingSearch
from graph_store import GraphStore
from extractor import TripleExtractor


# Setup logging (never to stdout -- that is the MCP wire)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)


def _build_connector(name: str, ctype: str, cfg: Dict[str, Any]) -> Any:
    from connectors import GitHubConnector, SlackExportConnector
    if ctype == "filesystem":
        return FilesystemConnector(name, cfg)
    if ctype == "github":
        return GitHubConnector(name, cfg)
    if ctype == "slack":
        return SlackExportConnector(name, cfg)
    logger.error(f"Unknown connector type: {ctype}")
    return None


def _create_sync_manager() -> SyncManager:
    sync = SyncManager()
    # Always sync the local knowledge directory first.
    sync.add_connector(FilesystemConnector("knowledge", {"root": str(KNOWLEDGE_DIR)}))
    # Optionally load additional connectors from COMPANY_BRAIN_CONNECTORS env var.
    if CONNECTORS_JSON:
        try:
            for entry in json.loads(CONNECTORS_JSON):
                conn = _build_connector(entry["name"], entry["type"], entry.get("config", {}))
                if conn:
                    sync.add_connector(conn)
        except Exception as e:
            logger.error(f"Failed to parse COMPANY_BRAIN_CONNECTORS: {e}")
    return sync


# Build the knowledge base ONCE, when the server process starts.
permission_manager = PermissionManager()
embedding_search = EmbeddingSearch()

sync_manager = _create_sync_manager()
logger.info("Syncing documents from configured connectors...")
documents = sync_manager.sync()
logger.info(f"Loaded {len(documents)} documents")

loader = DocumentLoader()
loader.documents = {doc.id: doc for doc in documents}

logger.info("Indexing documents for semantic search...")
embedding_search.index_documents(documents)

logger.info("Building knowledge graph from documents...")
graph_store = GraphStore(BASE_DIR / "data" / "graph.db")
extractor = TripleExtractor()
graph_store.ingest_documents(documents, extractor)

tools = MCPTools(loader, permission_manager, embedding_search, graph_store)

mcp = MCPServer(MCP_SERVER_NAME, version=MCP_SERVER_VERSION)


def _to_dict(result: ToolResult) -> Dict[str, Any]:
    """Serialize a ToolResult for the wire."""
    return {
        "success": result.success,
        "data": result.data,
        "citations": result.citations or [],
        "error": result.error,
    }


@mcp.tool()
def list_policies() -> Dict[str, Any]:
    """List all policy documents."""
    logger.info("Tool call: list_policies")
    return _to_dict(tools.list_policies())


@mcp.tool()
def read_document(doc_id: str) -> Dict[str, Any]:
    """Read a specific document by ID (e.g. 'policies/security_policy')."""
    logger.info(f"Tool call: read_document doc_id={doc_id}")
    return _to_dict(tools.read_document(doc_id))


@mcp.tool()
def search_documents(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """Search documents by query, optionally restricted to one category."""
    logger.info(f"Tool call: search_documents query={query!r} category={category}")
    return _to_dict(tools.search_documents(query, category))


@mcp.tool()
def find_meeting_notes(query: str) -> Dict[str, Any]:
    """Find meeting notes matching a query."""
    logger.info(f"Tool call: find_meeting_notes query={query!r}")
    return _to_dict(tools.find_meeting_notes(query))


@mcp.tool()
def list_categories() -> Dict[str, Any]:
    """List all categories accessible to the server role."""
    logger.info("Tool call: list_categories")
    return _to_dict(tools.list_categories())


@mcp.tool()
def why(entity: str) -> Dict[str, Any]:
    """Explain the rationale, actors, and relationships around an entity or decision (e.g. 'authentication decision' or 'Q4 2024')."""
    logger.info(f"Tool call: why entity={entity!r}")
    return _to_dict(tools.why(entity))


if __name__ == "__main__":
    logger.info(f"Starting MCP server (stdio) with role={SERVER_ROLE}...")
    mcp.run()
