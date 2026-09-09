"""
Metrics for evaluating Company Brain Agent performance.
"""

import logging
import re
from typing import List, Any

from agent.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


def _normalize_citations(citations: List[Any]) -> List[str]:
    """Extract unique document IDs from a list of citation entries."""
    seen = set()
    out = []
    for citation in citations:
        cid = citation.get("id", "") if isinstance(citation, dict) else str(citation)
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


class EvaluationMetrics:
    """Calculate evaluation metrics for agent performance."""

    def __init__(self, llm_client: OllamaClient = None):
        self.llm_client = llm_client or OllamaClient()

    def calculate_precision(self, predicted_citations: List[Any], expected_citations: List[str]) -> float:
        """Citation precision: fraction of predicted citations that are expected (deduplicated by doc ID)."""
        predicted_ids = _normalize_citations(predicted_citations)
        if not predicted_ids:
            return 0.0
        correct = set(predicted_ids) & set(expected_citations)
        return len(correct) / len(predicted_ids)

    def calculate_recall(self, predicted_citations: List[Any], expected_citations: List[str]) -> float:
        """Citation recall: fraction of expected citations that were predicted (deduplicated by doc ID)."""
        if not expected_citations:
            return 1.0
        predicted_ids = _normalize_citations(predicted_citations)
        correct = set(predicted_ids) & set(expected_citations)
        return len(correct) / len(expected_citations)

    def calculate_f1(self, precision: float, recall: float) -> float:
        """Calculate F1 score from precision and recall."""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def calculate_correctness(self, question: str, expected_answer: str, predicted_answer: str) -> float:
        """LLM-as-judge: does the predicted answer contain the facts in the expected answer?"""
        prompt = f"""You are an evaluator. Given the question, expected answer, and predicted answer, determine whether the predicted answer contains the key facts from the expected answer. Be lenient about wording and small omissions; focus on whether the main claims are present.

Question: {question}
Expected answer: {expected_answer}
Predicted answer: {predicted_answer}

Does the predicted answer contain the main facts in the expected answer? Start your response with exactly one word: Yes or No."""

        try:
            response = (self.llm_client.generate(prompt) or "").strip()
            logger.info(f"Correctness judge response: {response!r}")
            lowered = response.lower()
            has_yes = re.search(r'\byes\b', lowered) is not None
            has_no = re.search(r'\bno\b', lowered) is not None
            if has_yes and not has_no:
                return 1.0
            if has_no and not has_yes:
                return 0.0
            # Ambiguous or empty: fall back to first token.
            tokens = response.split()
            if tokens:
                first = tokens[0].lower().strip(".,")
                return 1.0 if first == "yes" else 0.0
            return 0.0
        except Exception as e:
            logger.error(f"Error judging correctness: {e}")
            return 0.0
