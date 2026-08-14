"""
Semantic search using vector embeddings for Company Brain MCP Server.
Uses Ollama for embeddings.
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
import requests
import logging

from config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL
from document_loader import Document

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from semantic search."""
    document: Document
    score: float
    snippet: str


class EmbeddingSearch:
    """Semantic search using Ollama embeddings."""
    
    def __init__(self):
        logger.info(f"Using Ollama embeddings: {OLLAMA_EMBEDDING_MODEL}")
        self.base_url = OLLAMA_BASE_URL
        self.model = OLLAMA_EMBEDDING_MODEL
        self.document_embeddings: Dict[str, np.ndarray] = {}
        self.documents: Dict[str, Document] = {}
    
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
    
    def index_documents(self, documents: List[Document]):
        """Index documents for semantic search."""
        logger.info(f"Indexing {len(documents)} documents with Ollama...")
        
        for doc in documents:
            self.documents[doc.id] = doc
            # Embed both title and content for better search
            text_to_embed = f"{doc.title}\n\n{doc.content}"
            embedding = self._get_embedding(text_to_embed)
            self.document_embeddings[doc.id] = embedding
        
        logger.info("Document indexing complete")
    
    def search(self, query: str, top_k: int = 5, category: str = None) -> List[SearchResult]:
        """Search documents by semantic similarity."""
        if not self.document_embeddings:
            logger.warning("No documents indexed for search")
            return []
        
        # Embed the query
        query_embedding = self._get_embedding(query)
        
        # Calculate cosine similarity
        results = []
        for doc_id, doc_embedding in self.document_embeddings.items():
            doc = self.documents[doc_id]
            
            # Filter by category if specified
            if category and doc.category != category:
                continue
            
            # Cosine similarity
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )
            
            # Create snippet
            snippet = self._create_snippet(doc.content, query)
            
            results.append(SearchResult(
                document=doc,
                score=float(similarity),
                snippet=snippet
            ))
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def _create_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Create a snippet highlighting relevant parts."""
        query_words = set(query.lower().split())
        sentences = content.split('.')
        
        # Score sentences by query word overlap
        scored_sentences = []
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            overlap = len(query_words & sentence_words)
            scored_sentences.append((overlap, sentence))
        
        # Get best sentence
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        if scored_sentences and scored_sentences[0][0] > 0:
            snippet = scored_sentences[0][1].strip()
        else:
            snippet = content[:max_length]
        
        # Truncate if too long
        if len(snippet) > max_length:
            snippet = snippet[:max_length] + "..."
        
        return snippet
    
    def get_document_embedding(self, doc_id: str) -> np.ndarray:
        """Get embedding for a specific document."""
        return self.document_embeddings.get(doc_id)
