# Company Brain MCP

A local AI assistant that answers questions across a company's internal knowledge using the Model Context Protocol (MCP).

## Overview

Company Brain MCP provides controlled access to internal company documents through MCP tools, enabling AI agents to query policies, product documentation, meeting notes, and engineering documentation with proper access control and citation support.

## Architecture

```
User
  ↓
LLM / Agent
  ↓
MCP Client
  ↓
Local MCP Server
  ↓
┌──────────────┬──────────────┬──────────────┐
Policies       Product Docs   Meeting Notes
Engineering    Architecture   Internal FAQs
└──────────────┴──────────────┴──────────────┘
  ↓
Grounded answer + citations
```

## Features

- **MCP Tools**: `search_documents()`, `read_document()`, `list_policies()`, `find_meeting_notes()`
- **Access Control**: Role-based permissions (admin, engineer, product, hr, guest)
- **Semantic Search**: Vector embeddings for document search
- **Citations**: Source tracking for all answers
- **Audit Logging**: Complete audit trail of all queries
- **Read-Only**: All tools are read-only for safety

## Installation

```bash
cd company-brain-mcp
pip install -r requirements.txt
```

## Usage

### Start the MCP Server

```bash
cd server
python mcp_server.py
```

### Available Tools

1. **list_policies** - List all policy documents
2. **read_document** - Read a specific document by ID
3. **search_documents** - Search documents by query
4. **find_meeting_notes** - Find meeting notes matching a query
5. **list_categories** - List all accessible categories

### Example Queries

- "What is our AI deployment policy?"
- "What decisions were made about authentication last month?"
- "What's on the product roadmap for Q4?"
- "Show me all security policies"

## Project Structure

```
company-brain-mcp/
├── server/
│   ├── mcp_server.py       # Main MCP server
│   ├── tools.py            # MCP tools implementation
│   ├── permissions.py      # Access control system
│   ├── document_loader.py  # Document loading
│   ├── embeddings.py       # Semantic search
│   └── config.py           # Configuration
├── agent/
│   ├── assistant.py        # LLM agent
│   └── citation_formatter.py
├── knowledge/
│   ├── policies/           # Company policies
│   ├── product/            # Product documentation
│   ├── engineering/        # Technical docs
│   ├── meetings/           # Meeting notes
│   └── internal/           # Internal docs
├── evals/
│   ├── questions.json      # Test questions
│   └── evaluator.py
├── tests/
└── README.md
```

## Permissions

| Role      | Policies | Product | Engineering | Meetings | Internal |
|-----------|----------|---------|-------------|----------|----------|
| Admin     | ✓        | ✓       | ✓           | ✓        | ✓        |
| Engineer  | ✗        | ✓       | ✓           | ✓        | ✗        |
| Product   | ✓        | ✓       | ✗           | ✓        | ✗        |
| HR        | ✓        | ✗       | ✗           | ✓        | ✓        |
| Guest     | ✗        | ✓       | ✗           | ✗        | ✗        |

## Development

### Adding Documents

Add markdown, text, or JSON files to the appropriate `knowledge/` subdirectory. Documents are automatically loaded on server startup.

### Adding Tools

1. Implement the tool in `server/tools.py`
2. Add the tool definition in `server/mcp_server.py` under `_handle_tools_list`
3. Add the tool handler in `_handle_tool_call`

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Run evaluation
python evals/evaluator.py
```

## License

MIT
