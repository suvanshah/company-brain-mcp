"""
Configuration for Company Brain MCP Server.
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

# Knowledge base directories
POLICIES_DIR = KNOWLEDGE_DIR / "policies"
PRODUCT_DIR = KNOWLEDGE_DIR / "product"
ENGINEERING_DIR = KNOWLEDGE_DIR / "engineering"
MEETINGS_DIR = KNOWLEDGE_DIR / "meetings"
INTERNAL_DIR = KNOWLEDGE_DIR / "internal"

# Server settings
MCP_SERVER_NAME = "company-brain"
MCP_SERVER_VERSION = "0.1.0"

# Role enforced by the server. The deployment sets this; clients cannot override it.
# Options: admin, engineer, product, hr, guest
SERVER_ROLE = os.getenv("COMPANY_BRAIN_ROLE", "guest")

# Ollama settings
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.2")

# LLM settings for agent
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 1000

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "logs" / "mcp_server.log"

# Audit logging
AUDIT_LOG_FILE = BASE_DIR / "logs" / "audit.log"

# Connector configuration (loaded by SyncManager).
# Each entry has: source, type, config dict.
# Set COMPANY_BRAIN_CONNECTORS as a JSON string, e.g.:
# '[{"name": "engineering-wiki", "type": "github", "config": {"owner": "myorg", "repo": "wiki", "category": "engineering"}}]'
CONNECTORS_JSON = os.getenv("COMPANY_BRAIN_CONNECTORS", "")

# Reranker model. Set to a sentence-transformers cross-encoder name to enable neural reranking.
# Example: cross-encoder/ms-marco-MiniLM-L-6-v2
# Leave unset to use the lightweight keyword reranker fallback.
RERANKER_MODEL = os.getenv("COMPANY_BRAIN_RERANKER_MODEL")

# HTTP server settings
HTTP_HOST = os.getenv("COMPANY_BRAIN_HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.getenv("COMPANY_BRAIN_HTTP_PORT", "8000"))
# API key for the HTTP MCP endpoint. Leave unset for local development (not recommended in production).
API_KEY = os.getenv("COMPANY_BRAIN_API_KEY")
