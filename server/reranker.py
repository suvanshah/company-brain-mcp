"""
Reranking for Company Brain.

Supports a pluggable reranker. The default CrossEncoderReranker uses sentence-transformers
if installed; otherwise falls back to a lightweight keyword-based reranker.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger(__name__)


class Reranker(ABC):
    """Abstract reranker."""

    @abstractmethod
    def rerank(self, query: str, texts: List[str]) -> List[float]:
        """Return a score for each (query, text) pair. Higher is better."""
        raise NotImplementedError


class NoOpReranker(Reranker):
    """Pass-through reranker that returns 0 for all texts."""

    def rerank(self, query: str, texts: List[str]) -> List[float]:
        return [0.0] * len(texts)


class KeywordReranker(Reranker):
    """Lightweight fallback reranker that rewards exact/phrase matches."""

    def rerank(self, query: str, texts: List[str]) -> List[float]:
        scores = []
        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))
        for text in texts:
            text_lower = text.lower()
            # Phrase match bonus
            score = 1.0 if query_lower in text_lower else 0.0
            # Token overlap bonus
            text_tokens = set(re.findall(r"\w+", text_lower))
            overlap = query_tokens & text_tokens
            if query_tokens:
                score += len(overlap) / len(query_tokens)
            scores.append(score)
        return scores


class CrossEncoderReranker(Reranker):
    """Neural cross-encoder reranker using sentence-transformers."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading cross-encoder reranker: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
        except Exception as e:
            logger.error(f"Could not load cross-encoder reranker: {e}")
            raise

    def rerank(self, query: str, texts: List[str]) -> List[float]:
        if not texts:
            return []
        self._load_model()
        pairs = [[query, text] for text in texts]
        scores = self._model.predict(pairs, show_progress_bar=False)
        # sentence-transformers CrossEncoder predict returns numpy array or list of floats
        return [float(s) for s in scores]


def create_reranker(model_name: str = None) -> Reranker:
    """Factory for reranker.

    If a model_name is explicitly provided, try CrossEncoderReranker.
    Otherwise default to KeywordReranker for zero-dependency operation.
    If sentence-transformers is installed, you can set
    COMPANY_BRAIN_RERANKER_MODEL to enable the neural reranker.
    """
    import os
    env_model = os.getenv("COMPANY_BRAIN_RERANKER_MODEL")
    requested = model_name or env_model
    if requested:
        try:
            return CrossEncoderReranker(model_name=requested)
        except Exception:
            logger.warning("Falling back to keyword reranker because cross-encoder could not load")
    return KeywordReranker()
