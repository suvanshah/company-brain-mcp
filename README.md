# Company Brain MCP

A local AI assistant that answers questions across a company's internal knowledge using the Model Context Protocol (MCP).

## Overview

Company Brain MCP provides controlled access to internal company documents through MCP tools, enabling AI agents to query policies, product documentation, meeting notes, and engineering documentation with proper access control, grounded citations, and persistent search indexes.

## Architecture

```
User (Streamlit / Slack / CLI / Claude Desktop)
  ↓
LLM Agent (ReAct tool loop, conversation memory)
  ↓
MCP Client (stdio or HTTP)
  ↓
MCP Server
  ↓
┌─────────────────┬─────────────────┬─────────────────┐
│  Connectors     │  Chunker        │  Permissions    │
│  (filesystem,   │  (markdown-     │  (server-side   │
│   GitHub,       │   aware)        │   role)         │
│   Slack export) │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
  ↓
Persistent ChromaDB index + BM25 + optional reranker
  ↓
Grounded answer + section-aware citations
```

## Features

- **MCP Tools**: `search_documents`, `read_document`, `list_policies`, `find_meeting_notes`, `list_categories`
- **Real MCP transport**: stdio subprocess for local use; Streamable HTTP + API-key auth for deployment
- **Access Control**: Server-side role permissions enforced by the server, not the client
- **Hybrid Search**: Vector embeddings (Ollama `nomic-embed-text`) + BM25 over chunks
- **Reranker**: Pluggable cross-encoder or keyword reranker to improve retrieval precision
- **Chunking**: Markdown-aware chunking that preserves document and section context
- **Citations**: Section-aware sources from actual MCP tool results
- **Multi-turn Memory**: Conversation history fed into the LLM context
- **Persistent Vector Store**: ChromaDB with content-hash incremental sync
- **Connectors**: Filesystem, GitHub, and Slack export connectors with a sync manager
- **Agentic ReAct Loop**: LLM chooses which MCP tools to call and iterates
- **Evaluation**: Citation precision/recall + LLM-as-judge correctness

## Installation

```bash
cd company-brain-mcp
pip install -r requirements.txt
```

Optional for neural reranking:

```bash
pip install sentence-transformers
```

## Prerequisites

Ollama must be running with both models pulled:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

## Configuration

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPANY_BRAIN_ROLE` | `guest` | Server role: `admin`, `engineer`, `product`, `hr`, `guest` |
| `COMPANY_BRAIN_MCP_URL` | — | If set, agent connects over HTTP instead of stdio |
| `COMPANY_BRAIN_API_KEY` | — | API key for HTTP transport |
| `COMPANY_BRAIN_RERANKER_MODEL` | — | Cross-encoder model name (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) |
| `COMPANY_BRAIN_CONNECTORS` | — | JSON list of extra connector configs |

## Usage

### Web UI (Streamlit)

```bash
COMPANY_BRAIN_ROLE=admin streamlit run ui/app.py --server.port 8502
```

Then open `http://localhost:8502`.

### Terminal

```bash
COMPANY_BRAIN_ROLE=admin python -m agent.assistant
```

### MCP Server (stdio)

Useful for connecting from Claude Desktop, MCP Inspector, etc.:

```bash
COMPANY_BRAIN_ROLE=admin python server/mcp_server.py
# or, with the Inspector UI:
COMPANY_BRAIN_ROLE=admin npx @modelcontextprotocol/inspector python server/mcp_server.py
```

### MCP Server (HTTP)

Run the server over Streamable HTTP with optional API-key auth:

```bash
COMPANY_BRAIN_ROLE=admin \
COMPANY_BRAIN_API_KEY=secret \
python server/http_server.py
```

Connect the agent over HTTP:

```bash
export COMPANY_BRAIN_MCP_URL=http://127.0.0.1:8000/mcp
export COMPANY_BRAIN_API_KEY=secret
python -m agent.assistant
```

### Evaluation

```bash
COMPANY_BRAIN_ROLE=admin python -m evals.evaluator
```

This produces `evals/results.json` with citation precision/recall/F1 and LLM-as-judge correctness scores.

## Connectors

The `SyncManager` (`connectors/sync_manager.py`) loads documents from configured connectors, hashes their content, and only re-indexes changed or new documents.

### Filesystem (default)

Loads `knowledge/` subdirectories (`policies`, `product`, `engineering`, `meetings`, `internal`).

### GitHub

```bash
export COMPANY_BRAIN_CONNECTORS='[
  {"name": "eng-wiki", "type": "github", "config": {"owner": "myorg", "repo": "wiki", "path": "docs", "category": "engineering"}}
]'
COMPANY_BRAIN_ROLE=admin python server/mcp_server.py
```

For private repos, add a GitHub token to the connector config:

```json
{"token": "ghp_..."}
```

### Slack Export

```bash
export COMPANY_BRAIN_CONNECTORS='[
  {"name": "slack-export", "type": "slack", "config": {"export_path": "/path/to/slack_export.zip", "category": "meetings"}}
]'
```

## Permissions

The role is enforced on the server. Clients cannot pass a `role` argument to tools.

| Role      | Policies | Product | Engineering | Meetings | Internal |
|-----------|----------|---------|-------------|----------|----------|
| Admin     | ✓        | ✓       | ✓           | ✓        | ✓        |
| Engineer  | ✗        | ✓       | ✓           | ✓        | ✗        |
| Product   | ✓        | ✓       | ✗           | ✓        | ✗        |
| HR        | ✓        | ✗       | ✗           | ✓        | ✓        |
| Guest     | ✗        | ✓       | ✗           | ✗        | ✗        |

## Project Structure

```
company-brain-mcp/
├── agent/
│   ├── assistant.py          # ReAct agent + LLM loop
│   ├── conversation_history.py
│   ├── ollama_client.py
│   ├── prompt_templates.py
│   └── citation_formatter.py
├── server/
│   ├── mcp_server.py           # stdio MCP server entrypoint
│   ├── http_server.py          # HTTP MCP server entrypoint
│   ├── auth.py                 # API-key middleware
│   ├── tools.py                # MCP tool implementations
│   ├── permissions.py          # Role-based access control
│   ├── chunker.py              # Markdown-aware chunking
│   ├── document_loader.py      # Document model
│   ├── embeddings.py           # ChromaDB + BM25 + reranker
│   ├── reranker.py             # Pluggable reranker
│   └── config.py               # Configuration
├── connectors/
│   ├── base.py
│   ├── filesystem.py
│   ├── github.py
│   ├── slack.py
│   └── sync_manager.py
├── knowledge/
│   ├── policies/
│   ├── product/
│   ├── engineering/
│   ├── meetings/
│   └── internal/
├── ui/
│   └── app.py                  # Streamlit interface
├── evals/
│   ├── evaluator.py
│   ├── metrics.py
│   └── questions.json
├── data/                       # ChromaDB + sync state (created at runtime)
├── logs/
└── README.md
```

## Development

### Adding Documents

Add markdown, text, or JSON files to `knowledge/<category>/`. The server indexes them automatically on startup, and only changed documents are re-embedded.

### Adding Tools

1. Implement the tool logic in `server/tools.py`.
2. Register it in `server/mcp_server.py` with a `@mcp.tool()`-decorated wrapper.
3. Describe it in `agent/prompt_templates.py` if the agent should use it.

### Running Tests

```bash
# Run evaluation
COMPANY_BRAIN_ROLE=admin python -m evals.evaluator

# Run unit tests (when added)
python -m pytest tests/
```

## License

MIT
