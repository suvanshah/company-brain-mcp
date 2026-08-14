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
