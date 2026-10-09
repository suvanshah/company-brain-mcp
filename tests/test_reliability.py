"""
Reliability tests for Company Brain MCP.

Covers retrieval/chunking, document loading, filesystem and sync connectors,
and the MCP tool surface (read/search/list/find).

Run with: python -m unittest tests/test_reliability.py
"""

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(PROJECT_ROOT, "server")

# Make both the server modules and the connectors package importable.
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Stub out the heavy embeddings module before importing server.tools.
sys.modules["embeddings"] = types.SimpleNamespace(
    EmbeddingSearch=type("EmbeddingSearch", (), {})
)

os.environ.setdefault("COMPANY_BRAIN_ROLE", "guest")

import chunker
from document_loader import Document, DocumentLoader
from connectors.filesystem import FilesystemConnector
from connectors.sync_manager import SyncManager
from connectors.base import BaseConnector, ConnectorDocument
import tools
import permissions


class TestChunker(unittest.TestCase):
    def _doc(self, content, title="Doc"):
        return Document(
            id="doc/1",
            title=title,
            content=content,
            category="test",
            file_path="test/1.md",
            metadata={},
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

    def test_document_header_in_chunks(self):
        doc = self._doc("Paragraph one.\n\nParagraph two.")
        chunks = chunker.chunk_document(doc, max_chunk_tokens=100, overlap_tokens=10)
        self.assertTrue(chunks)
        for c in chunks:
            self.assertIn("Document: Doc", c.content)

    def test_heading_sections_preserved(self):
        doc = self._doc("# Title\n\n## Intro\n\nintro text.\n\n## Details\n\ndetail text.")
        chunks = chunker.chunk_document(doc)
        sections = [c.section for c in chunks]
        self.assertIn("Intro", sections)
        self.assertIn("Details", sections)

    def test_chunk_size_respects_limit(self):
        long_text = "word " * 2000
        doc = self._doc(long_text)
        chunks = chunker.chunk_document(doc, max_chunk_tokens=20, overlap_tokens=5)
        max_chars = 20 * 4
        for c in chunks:
            self.assertLessEqual(len(c.content), max_chars, "Chunk exceeded character budget")

    def test_chunk_ids_are_unique(self):
        doc = self._doc("## A\n\none.\n\n## B\n\ntwo.")
        chunks = chunker.chunk_document(doc)
        ids = [c.id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))


class TestDocumentLoader(unittest.TestCase):
    def test_load_markdown_from_directory(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "test.md").write_text("# Hello\n\ncontent here", encoding="utf-8")
            loader = DocumentLoader()
            docs = loader.load_category("test", Path(d))
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].title, "Hello")
            self.assertEqual(docs[0].category, "test")

    def test_get_documents_by_category(self):
        loader = DocumentLoader()
        loader.documents = {
            "a/x": Document(
                id="a/x",
                title="x",
                content="c",
                category="a",
                file_path="a/x.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            ),
            "a/y": Document(
                id="a/y",
                title="y",
                content="c",
                category="a",
                file_path="a/y.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            ),
            "b/z": Document(
                id="b/z",
                title="z",
                content="c",
                category="b",
                file_path="b/z.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            ),
        }
        self.assertEqual(len(loader.get_documents_by_category("a")), 2)
        self.assertEqual(len(loader.get_documents_by_category("b")), 1)


class TestFilesystemConnector(unittest.TestCase):
    def test_fetch_md_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "product").mkdir()
            (root / "product" / "roadmap.md").write_text("# Roadmap\n\nQ4", encoding="utf-8")
            (root / "product" / "data.json").write_text(
                json.dumps({"title": "Data", "content": "numbers"}), encoding="utf-8"
            )
            conn = FilesystemConnector("fs", {"root": str(root), "category": "product"})
            docs = conn.fetch()
            self.assertEqual(len(docs), 2)
            titles = {d.title for d in docs}
            self.assertIn("Roadmap", titles)
            self.assertIn("Data", titles)
            for d in docs:
                self.assertEqual(d.category, "product")

    def test_health_check_fails_for_missing_root(self):
        conn = FilesystemConnector("fs", {"root": "/nonexistent/path"})
        self.assertFalse(conn.health_check())

    def test_category_derived_from_parent_directory(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "engineering").mkdir()
            (Path(d) / "engineering" / "api.md").write_text("api", encoding="utf-8")
            conn = FilesystemConnector("fs", {"root": d})  # no explicit category
            docs = conn.fetch()
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].category, "engineering")


class TestSyncManager(unittest.TestCase):
    def test_sync_aggregates_documents_and_saves_state(self):
        class FakeConnector(BaseConnector):
            def fetch(self):
                return [
                    ConnectorDocument(
                        source_id="test/one",
                        title="One",
                        content="hello",
                        category="test",
                        file_path="test/one.md",
                        metadata={},
                        created_at="2024-01-01",
                        updated_at="2024-01-01",
                        source="fake",
                    )
                ]

        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "state.json"
            sm = SyncManager(state_path=state)
            sm.add_connector(FakeConnector("fake", {}))
            docs = sm.sync()
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].id, "test/one")
            self.assertEqual(docs[0].source, "fake")
            self.assertTrue(state.exists())

    def test_get_changed_doc_ids(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "state.json"
            sm = SyncManager(state_path=state)
            doc = Document(
                id="test/one",
                title="One",
                content="hello",
                category="test",
                file_path="test/one.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            )
            sm._state = {"test/one": {"hash": "wrong"}}
            changed = sm.get_changed_doc_ids([doc])
            self.assertEqual(changed, ["test/one"])


class TestMcpTools(unittest.TestCase):
    def setUp(self):
        self.pm = permissions.PermissionManager()
        self.loader = DocumentLoader()
        self.loader.documents = {
            "policies/security_policy": Document(
                id="policies/security_policy",
                title="Security Policy",
                content="MFA required",
                category="policies",
                file_path="knowledge/policies/security_policy.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            ),
            "meetings/roadmap_planning_2024_06": Document(
                id="meetings/roadmap_planning_2024_06",
                title="Roadmap Planning",
                content="discussed q3 goals",
                category="meetings",
                file_path="knowledge/meetings/roadmap_planning_2024_06.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            ),
            "product/product_roadmap": Document(
                id="product/product_roadmap",
                title="Product Roadmap",
                content="q4 roadmap",
                category="product",
                file_path="knowledge/product/product_roadmap.md",
                metadata={},
                created_at="2024-01-01",
                updated_at="2024-01-01",
            ),
        }

    def _tools(self, role, embedding=None):
        tools.SERVER_ROLE = role
        return tools.MCPTools(self.loader, self.pm, embedding)

    def test_list_policies_admin(self):
        result = self._tools("admin").list_policies()
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["id"], "policies/security_policy")

    def test_list_policies_guest_denied(self):
        result = self._tools("guest").list_policies()
        self.assertFalse(result.success)

    def test_find_meeting_notes(self):
        result = self._tools("product").find_meeting_notes("q3")
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["title"], "Roadmap Planning")

    def test_list_categories(self):
        result = self._tools("engineer").list_categories()
        self.assertTrue(result.success)
        self.assertEqual({c["category"] for c in result.data}, {"product", "engineering", "meetings"})

    def test_search_uses_embedding_results_when_available(self):
        from chunker import Chunk

        class FakeEmbeddingSearch:
            def __init__(self, loader):
                self.loader = loader

            def search(self, query, top_k, category):
                doc = self.loader.documents["product/product_roadmap"]
                chunk = Chunk(id="c1", document=doc, section="Overview", content="q4 roadmap")
                return [types.SimpleNamespace(chunk=chunk, score=1.0, snippet="q4 roadmap")]

        result = self._tools("guest", FakeEmbeddingSearch(self.loader)).search_documents(
            "roadmap", category="product"
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.data[0]["title"], "Product Roadmap")
        self.assertEqual(result.data[0]["snippet"], "q4 roadmap")

    def test_search_fallback_text_search(self):
        result = self._tools("guest").search_documents("roadmap", category="product")
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 1)


if __name__ == "__main__":
    unittest.main()
