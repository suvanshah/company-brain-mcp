"""
Security tests for Company Brain MCP.

These tests cover:
- Role-based permission matrix
- Tool-level permission enforcement (read / search)
- Search result content leakage
- Auth token extraction (when starlette is installed)

Run with: python -m unittest tests/test_security.py
"""

import importlib.util
import os
import sys
import types
import unittest

# The server modules live in the server/ directory and are not a package.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(PROJECT_ROOT, "server")
sys.path.insert(0, SERVER_DIR)

# Stub out the heavy embeddings module before importing server.tools.
sys.modules["embeddings"] = types.SimpleNamespace(
    EmbeddingSearch=type("EmbeddingSearch", (), {})
)

# Ensure a default role is set before modules that read it are imported.
os.environ.setdefault("COMPANY_BRAIN_ROLE", "guest")

import permissions as p
import tools
from document_loader import Document, DocumentLoader

HAS_STARLETTE = importlib.util.find_spec("starlette") is not None


class TestPermissionMatrix(unittest.TestCase):
    def setUp(self):
        self.pm = p.PermissionManager()

    def test_role_matrix(self):
        expected = {
            "admin": {"policies", "product", "engineering", "meetings", "internal"},
            "engineer": {"product", "engineering", "meetings"},
            "product": {"product", "meetings", "policies"},
            "hr": {"policies", "internal", "meetings"},
            "guest": {"product"},
        }
        for role, cats in expected.items():
            r = self.pm.role_from_string(role)
            self.assertEqual(self.pm.get_accessible_categories(r), set(cats))

    def test_unknown_role_defaults_to_guest(self):
        r = self.pm.role_from_string("intruder")
        self.assertEqual(self.pm.get_accessible_categories(r), {"product"})

    def test_read_and_search_same_categories(self):
        for role in ["admin", "engineer", "product", "hr", "guest"]:
            r = self.pm.role_from_string(role)
            for cat in self.pm.get_accessible_categories(r):
                self.assertTrue(self.pm.can_read_document(r, cat))
                self.assertTrue(self.pm.can_search_category(r, cat))


class TestToolPermissions(unittest.TestCase):
    def setUp(self):
        self.pm = p.PermissionManager()
        self.loader = DocumentLoader()
        self.loader.documents = {
            "product/roadmap": Document(
                id="product/roadmap",
                title="Product Roadmap",
                content="roadmap q4 2024",
                category="product",
                file_path="knowledge/product/roadmap.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-09-09",
            ),
            "engineering/api_architecture": Document(
                id="engineering/api_architecture",
                title="API Architecture",
                content="api schema design",
                category="engineering",
                file_path="knowledge/engineering/api_architecture.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-09-09",
            ),
            "policies/security_policy": Document(
                id="policies/security_policy",
                title="Security Policy",
                content="do not share passwords",
                category="policies",
                file_path="knowledge/policies/security_policy.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-09-09",
            ),
            "internal/faqs": Document(
                id="internal/faqs",
                title="Internal FAQs",
                content="internal only",
                category="internal",
                file_path="knowledge/internal/faqs.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-09-09",
            ),
        }

    def _tools(self, role):
        tools.SERVER_ROLE = role
        return tools.MCPTools(self.loader, self.pm, None)

    def test_guest_cannot_read_engineering(self):
        result = self._tools("guest").read_document("engineering/api_architecture")
        self.assertFalse(result.success)
        self.assertIn("Permission denied", result.error)

    def test_guest_can_read_product(self):
        result = self._tools("guest").read_document("product/roadmap")
        self.assertTrue(result.success)
        self.assertEqual(result.data["title"], "Product Roadmap")

    def test_engineer_cannot_read_policies(self):
        result = self._tools("engineer").read_document("policies/security_policy")
        self.assertFalse(result.success)
        self.assertIn("Permission denied", result.error)

    def test_guest_search_limited_to_product(self):
        result = self._tools("guest").search_documents("roadmap")
        self.assertTrue(result.success)
        for item in result.data:
            self.assertEqual(item["category"], "product")

    def test_engineer_search_limited_to_allowed_categories(self):
        result = self._tools("engineer").search_documents("schema")
        self.assertTrue(result.success)
        for item in result.data:
            self.assertIn(item["category"], {"engineering", "product", "meetings"})

    def test_search_does_not_expose_full_content(self):
        """Search should only return snippets, not full document content."""
        result = self._tools("guest").search_documents("roadmap", category="product")
        self.assertTrue(result.success)
        self.assertGreater(len(result.data), 0)
        for item in result.data:
            self.assertNotIn("content", item)
            self.assertIn("snippet", item)


@unittest.skipUnless(HAS_STARLETTE, "starlette not installed")
class TestAuth(unittest.TestCase):
    def setUp(self):
        import auth
        self.auth = auth

    def _request(self, headers):
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp",
            "headers": [(k.encode(), v.encode()) for k, v in headers.items()],
        }
        return Request(scope, receive=None)

    def test_bearer_token_extraction(self):
        req = self._request({"authorization": "Bearer secret"})
        self.assertEqual(self.auth._get_api_key_from_request(req), "secret")

    def test_x_api_key_extraction(self):
        req = self._request({"x-api-key": "secret"})
        self.assertEqual(self.auth._get_api_key_from_request(req), "secret")

    def test_malformed_bearer_returns_empty(self):
        req = self._request({"authorization": "Bearer"})
        self.assertEqual(self.auth._get_api_key_from_request(req), "")

    def test_no_key_returns_empty(self):
        req = self._request({})
        self.assertEqual(self.auth._get_api_key_from_request(req), "")


if __name__ == "__main__":
    unittest.main()
