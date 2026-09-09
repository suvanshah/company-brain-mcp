"""
Authentication middleware for the Company Brain HTTP MCP server.

The server uses a simple API-key scheme by default. In production, replace this
with an OAuth2/JWT validator or a reverse proxy that terminates identity.
"""

import logging
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import SERVER_ROLE

logger = logging.getLogger(__name__)


def _get_api_key_from_request(request: Request) -> str:
    """Extract the API key from the Authorization header or X-API-Key header."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(None, 1)[1].strip()
    return request.headers.get("x-api-key", "")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates an API key before allowing access."""

    def __init__(self, app, api_key: str = None):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Health/readiness checks and CORS preflight can be public
        if request.url.path in ("/health", "/ready") or request.method == "OPTIONS":
            return await call_next(request)

        # No API key configured: allow all traffic (useful for local dev only)
        if not self.api_key:
            request.state.role = SERVER_ROLE
            request.state.user = "anonymous"
            return await call_next(request)

        provided = _get_api_key_from_request(request)
        if provided != self.api_key:
            logger.warning(f"Rejected request from {request.client}: invalid API key")
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        request.state.role = SERVER_ROLE
        request.state.user = "api-key-user"
        return await call_next(request)
