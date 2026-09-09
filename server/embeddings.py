"""
Hybrid semantic + keyword search over document chunks for Company Brain MCP Server.
Uses ChromaDB for persistent vector storage, Ollama for embeddings, and BM25 for
exact token matching.
"""

import hashlib
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
import logging

import numpy as np
from rank_bm25 import BM25Okapi
import chromadb

from config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL, BASE_DIR, RERANKER_MODEL
from document_loader import Document
from chunker import Chunk, chunk_document
from reranker import create_reranker

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a search."""
    chunk: Chunk
    score: float
    snippet: str


class EmbeddingSearch:
    """Hybrid semantic + keyword search over persistent document chunks."""

    def __init__(self, bm25_weight: float = 0.3, reranker_weight: float = 0.4):
        logger.info(f"Using Ollama embeddings: {OLLAMA_EMBEDDING_MODEL}")
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_EMBEDDING_MODEL
        self.bm25_weight = bm25_weight
        self.reranker_weight = reranker_weight

        # Persistent ChromaDB collection for chunk embeddings and metadata
        chroma_dir = BASE_DIR / "data" / "chroma"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name="company_brain",
            metadata={"hnsw:space": "cosine"},
        )

        self.documents: Dict[str, Document] = {}
        self.chunks: List[Chunk] = []
        self.chunk_by_id: Dict[str, Chunk] = {}
        self.bm25 = None
        self.bm25_chunk_ids: List[str] = []
        self.reranker = create_reranker(RERANKER_MODEL)

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding from Ollama."""
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            return np.array(response.json()["embedding"])
        except Exception as e:
            logger.error(f"Error getting embedding from Ollama: {e}")
            return np.zeros(768)  # Fallback to zeros

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text for BM25."""
        return re.findall(r"\w+", text.lower())

    @staticmethod
    def _doc_hash(doc: Document) -> str:
        """Stable content hash for a document."""
        return hashlib.md5(doc.content.encode("utf-8")).hexdigest()

    def index_documents(self, documents: List[Document]):
        """Index documents for semantic and keyword search, skipping unchanged docs."""
        logger.info(f"Indexing {len(documents)} documents with ChromaDB + BM25...")

        new_doc_hashes = {doc.id: self._doc_hash(doc) for doc in documents}
        new_doc_ids = set(new_doc_hashes.keys())

        # Load existing chunk metadata to detect changes
        existing = self.collection.get(include=["metadatas"])
        existing_ids = existing.get("ids", [])
        existing_metadatas = existing.get("metadatas", [])

        existing_doc_chunk_ids: Dict[str, List[str]] = {}
        existing_doc_hashes: Dict[str, str] = {}
        for chunk_id, meta in zip(existing_ids, existing_metadatas):
            doc_id = meta.get("doc_id")
            if doc_id:
                existing_doc_chunk_ids.setdefault(doc_id, []).append(chunk_id)
                existing_doc_hashes[doc_id] = meta.get("doc_hash", "")

        # Determine which docs are new/changed and which existing docs were removed
        docs_to_upsert_ids: set = set()
        chunk_ids_to_delete: List[str] = []

        for doc in documents:
            if existing_doc_hashes.get(doc.id) != new_doc_hashes[doc.id]:
                docs_to_upsert_ids.add(doc.id)
                chunk_ids_to_delete.extend(existing_doc_chunk_ids.get(doc.id, []))

        for doc_id in existing_doc_chunk_ids:
            if doc_id not in new_doc_ids:
                chunk_ids_to_delete.extend(existing_doc_chunk_ids[doc_id])

        if chunk_ids_to_delete:
            self.collection.delete(ids=chunk_ids_to_delete)
            logger.info(f"Deleted {len(chunk_ids_to_delete)} stale chunks")

        # Build the in-memory chunk list and upsert new/changed chunks
        all_chunks: List[Chunk] = []
        for doc in documents:
            self.documents[doc.id] = doc
            if doc.id in docs_to_upsert_ids:
                chunks = chunk_document(doc)
                embeddings = [self._get_embedding(c.content).tolist() for c in chunks]
                self.collection.upsert(
                    ids=[c.id for c in chunks],
                    embeddings=embeddings,
                    documents=[c.content for c in chunks],
                    metadatas=[{
                        "doc_id": doc.id,
                        "doc_title": doc.title,
                        "category": doc.category,
                        "section": c.section or "",
                        "doc_hash": new_doc_hashes[doc.id],
                    } for c in chunks]
                )
                all_chunks.extend(chunks)
            else:
                # Reuse existing chunks from ChromaDB
                ids = existing_doc_chunk_ids[doc.id]
                res = self.collection.get(ids=ids, include=["documents", "metadatas"])
                for chunk_id, content, meta in zip(res["ids"], res["documents"], res["metadatas"]):
                    section = meta.get("section") or None
                    all_chunks.append(Chunk(
                        id=chunk_id,
                        document=doc,
                        section=section,
                        content=content,
                    ))

        self.chunks = all_chunks
        self.chunk_by_id = {c.id: c for c in all_chunks}
        self.bm25_chunk_ids = [c.id for c in all_chunks]
        tokenized_corpus = [self._tokenize(c.content) for c in all_chunks]
        self.bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

        logger.info(f"Indexed {len(self.chunks)} chunks from {len(documents)} documents")
        logger.info("Document indexing complete")

    def _normalize(self, scores: List[float]) -> List[float]:
        """Min-max normalize scores to [0, 1]."""
        if not scores:
            return []
        lo, hi = min(scores), max(scores)
        if hi == lo:
            return [0.0] * len(scores)
        return [(s - lo) / (hi - lo) for s in scores]

    def search(self, query: str, top_k: int = 5, category: str = None) -> List[SearchResult]:
        """Search document chunks by hybrid semantic + keyword similarity, then rerank."""
        if not self.chunks or not self.bm25:
            logger.warning("No documents indexed for search")
            return []

        # Stage 1: retrieve a larger candidate set with vector + BM25
        candidates = self._hybrid_candidates(query, category, top_k=max(top_k * 3, 15))
        if not candidates:
            return []

        # Stage 2: rerank candidate chunks with the configured reranker
        texts = [c.chunk.content for c in candidates]
        try:
            rerank_scores = self.reranker.rerank(query, texts)
        except Exception as e:
            logger.warning(f"Reranker failed: {e}; using hybrid scores only")
            rerank_scores = [0.0] * len(candidates)

        norm_hybrid = self._normalize([c.score for c in candidates])
        norm_rerank = self._normalize(rerank_scores)

        final_scores = [
            (1 - self.reranker_weight) * h + self.reranker_weight * r
            for h, r in zip(norm_hybrid, norm_rerank)
        ]

        reranked = []
        for result, score in zip(candidates, final_scores):
            reranked.append(SearchResult(
                chunk=result.chunk,
                score=float(score),
                snippet=result.snippet,
            ))

        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]

    def _hybrid_candidates(self, query: str, category: str = None, top_k: int = 15) -> List[SearchResult]:
        """Stage 1 retrieval: vector + BM25 hybrid scoring."""
        query_embedding = self._get_embedding(query)
        query_tokens = self._tokenize(query)

        where = {"category": category} if category else None
        count = self.collection.count()
        n_results = max(top_k, min(count, 100))

        vector_result = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
            where=where,
            include=["distances"],
        )

        vector_ids = vector_result["ids"][0]
        vector_distances = vector_result["distances"][0]
        vector_scores = {cid: 1.0 - float(dist) for cid, dist in zip(vector_ids, vector_distances)}

        # BM25 keyword search over all chunks
        bm25_scores = list(self.bm25.get_scores(query_tokens)) if query_tokens else [0.0] * len(self.bm25_chunk_ids)
        bm25_by_id = dict(zip(self.bm25_chunk_ids, bm25_scores))

        # Combine scores over all chunks, normalizing each signal globally
        all_chunk_ids = self.bm25_chunk_ids
        vector_vals = [vector_scores.get(cid, 0.0) for cid in all_chunk_ids]
        bm25_vals = [bm25_by_id.get(cid, 0.0) for cid in all_chunk_ids]
        norm_vector = self._normalize(vector_vals)
        norm_bm25 = self._normalize(bm25_vals)

        combined = {
            cid: (1 - self.bm25_weight) * nv + self.bm25_weight * nb
            for cid, nv, nb in zip(all_chunk_ids, norm_vector, norm_bm25)
        }

        results = []
        for chunk in self.chunks:
            if category and chunk.document.category != category:
                continue
            score = combined.get(chunk.id, 0.0)
            snippet = self._create_snippet(chunk.content, query)
            results.append(SearchResult(
                chunk=chunk,
                score=float(score),
                snippet=snippet
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _create_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Create a snippet highlighting relevant parts."""
        query_words = set(query.lower().split())
        sentences = re.split(r'(?<=[.!?])\s+', content)

        scored_sentences = []
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(query_words & sentence_words)
            scored_sentences.append((overlap, sentence))

        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        if scored_sentences and scored_sentences[0][0] > 0:
            snippet = scored_sentences[0][1].strip()
        else:
            body = re.sub(r'^Document:.*?\n(?:Section:.*?\n\n)?', '', content, flags=re.DOTALL)
            snippet = body[:max_length].strip()

        if len(snippet) > max_length:
            snippet = snippet[:max_length] + "..."

        return snippet

    def get_document_embedding(self, doc_id: str) -> Optional[np.ndarray]:
        """Get embedding for a specific document (not stored by default)."""
        return None
