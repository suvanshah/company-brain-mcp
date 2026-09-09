"""
HTTP MCP server for Company Brain.

Exposes the same MCP tools as `mcp_server.py` but over Streamable HTTP, with
optional API-key authentication. stdout is not used for JSON-RPC here, so this
server is safe to run as a network service behind a reverse proxy.

Run from the project root:
    python server/http_server.py
"""

import logging
import sys

import uvicorn
from starlette.middleware.cors import CORSMiddleware

# Importing mcp_server sets up the knowledge base, permissions, and MCP tools.
# `mcp.run()` is guarded by `if __name__ == "__main__"`, so it will not start stdio.
import mcp_server as mcp_module  # noqa: E402

from config import HTTP_HOST, HTTP_PORT, API_KEY, LOG_LEVEL, LOG_FILE  # noqa: E402
from auth import APIKeyMiddleware  # noqa: E402

# Setup logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)


def build_app():
    """Build the Starlette ASGI app with MCP endpoint and auth middleware."""
    app = mcp_module.mcp.streamable_http_app(
        host=HTTP_HOST,
        stateless_http=True,
        json_response=True,
    )

    # API key middleware (inner layer)
    app = APIKeyMiddleware(app, api_key=API_KEY)

    # CORS middleware (outer layer) so OPTIONS preflight requests are handled
    # before auth checks
    app = CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )

    return app


if __name__ == "__main__":
    logger.info(f"Starting HTTP MCP server on {HTTP_HOST}:{HTTP_PORT} (API key required: {bool(API_KEY)})")
    app = build_app()
    uvicorn.run(app, host=HTTP_HOST, port=HTTP_PORT)
