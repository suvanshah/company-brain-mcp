"""
Lightweight SQLite knowledge graph for Company Brain.
Stores extracted triples (subject, predicate, object) with provenance.
"""

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from document_loader import Document

logger = logging.getLogger(__name__)


_EXTRACTOR_VERSION = "2"


class GraphStore:
    """Stores and queries entity/relation triples extracted from documents."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Allow the same connection to be used from any thread (MCP tools run on a worker thread).
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                doc_id TEXT PRIMARY KEY,
                doc_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                FOREIGN KEY (doc_id) REFERENCES sources(doc_id)
            );

            CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
            CREATE INDEX IF NOT EXISTS idx_triples_object ON triples(object);
            CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);
            """
        )
        self.conn.commit()

    @staticmethod
    def _doc_hash(content: str) -> str:
        # Include extractor version so prompt changes trigger re-extraction.
        return hashlib.md5(
            f"{content}|v{_EXTRACTOR_VERSION}".encode("utf-8")
        ).hexdigest()

    def ingest_document(self, doc: Document, extractor) -> int:
        """Extract triples from a document and store them, skipping unchanged docs."""
        new_hash = self._doc_hash(doc.content)
        row = self.conn.execute(
            "SELECT doc_hash FROM sources WHERE doc_id = ?", (doc.id,)
        ).fetchone()

        if row and row["doc_hash"] == new_hash:
            logger.debug(f"Graph triples up to date for {doc.id}")
            return 0

        # Extract new triples
        try:
            triples = extractor.extract(doc.content)
        except Exception as e:
            logger.warning(f"Failed to extract triples from {doc.id}: {e}")
            return 0

        if not isinstance(triples, list):
            logger.warning(f"Extractor for {doc.id} did not return a list of triples")
            return 0

        # Delete old triples for this doc
        self.conn.execute("DELETE FROM triples WHERE doc_id = ?", (doc.id,))
        self.conn.execute(
            "INSERT OR REPLACE INTO sources (doc_id, doc_hash) VALUES (?, ?)",
            (doc.id, new_hash),
        )

        count = 0
        for t in triples:
            if not all(k in t for k in ("subject", "predicate", "object")):
                continue
            self.conn.execute(
                "INSERT INTO triples (subject, predicate, object, doc_id, confidence) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    t.get("subject", ""),
                    t.get("predicate", ""),
                    t.get("object", ""),
                    doc.id,
                    t.get("confidence", 0.8),
                ),
            )
            count += 1

        self.conn.commit()
        logger.info(f"Stored {count} triples for {doc.id}")
        return count

    def ingest_documents(self, documents: List[Document], extractor):
        """Extract and store triples for a list of documents."""
        total = 0
        for doc in documents:
            total += self.ingest_document(doc, extractor)
        logger.info(f"Knowledge graph now contains triples from {len(documents)} documents")
        return total

    _STOPWORDS = {
        "the", "and", "for", "are", "was", "were", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "shall", "to", "of", "in", "on", "at", "by", "with",
        "from", "as", "is", "it", "its", "this", "that", "these", "those", "a",
        "an", "all", "any", "some", "many", "much", "more", "most", "other",
        "such", "only", "own", "same", "so", "than", "too", "very", "can", "just",
        "but", "not", "no", "nor", "or", "if", "then", "else", "when", "where",
        "why", "how", "what", "who", "which", "while", "because", "since", "until",
        "although", "though", "before", "after", "above", "below", "up", "down",
        "out", "off", "over", "under", "again", "further", "once",
    }

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Split text into words, keeping hyphen/dotted tokens such as 2.0 and customer-facing."""
        tokens = re.findall(r"\w+(?:[\-\.]\w+)*", text.lower())
        return [t for t in tokens if t not in GraphStore._STOPWORDS and len(t) > 1]

    @staticmethod
    def _contains_word(text: str, word: str) -> bool:
        """Check for a whole-word match in a string."""
        return f" {word} " in f" {text} "

    def find_related(self, entity: str, top_k: int = 20) -> List[Dict]:
        """Find triples where the query's content words appear as subject or object.

        Ranks by the number of whole-word token matches, then by extraction confidence,
        so the most relevant triples appear first instead of the model's most confident
        but unrelated triples.
        """
        words = self._tokenize(entity)
        if not words:
            return []

        # Fetch candidates: any triple that mentions at least one query word.
        conditions = []
        params = []
        for word in words:
            conditions.append("(subject LIKE ? OR object LIKE ?)")
            like = f"%{word}%"
            params.extend([like, like])

        where = " OR ".join(conditions)
        rows = self.conn.execute(
            f"SELECT subject, predicate, object, doc_id, confidence "
            f"FROM triples WHERE {where}",
            params,
        ).fetchall()

        # Re-rank using whole-word matches to avoid substring false positives (e.g. "for"
        # matching "performance") and to surface triples that contain more of the query.
        scored = []
        for r in rows:
            text = f"{r['subject']} {r['object']}".lower()
            score = sum(1 for w in words if self._contains_word(text, w))
            if score == 0:
                continue
            scored.append((score, r["confidence"], r))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        return [
            {
                "subject": r["subject"],
                "predicate": r["predicate"],
                "object": r["object"],
                "doc_id": r["doc_id"],
                "confidence": r["confidence"],
            }
            for _, _, r in scored[:top_k]
        ]

    def find_by_predicate(self, predicate: str, top_k: int = 20) -> List[Dict]:
        """Find triples by predicate."""
        rows = self.conn.execute(
            "SELECT subject, predicate, object, doc_id, confidence "
            "FROM triples WHERE predicate = ? "
            "ORDER BY confidence DESC LIMIT ?",
            (predicate, top_k),
        ).fetchall()
        return [dict(r) for r in rows]
