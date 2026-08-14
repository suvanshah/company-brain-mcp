"""
Metrics for evaluating Company Brain Agent performance.
"""

from typing import List, Dict, Set
import re


class EvaluationMetrics:
    """Calculate evaluation metrics for agent performance."""
    
    @staticmethod
    def calculate_precision(predicted_citations: List[str], expected_citations: List[str]) -> float:
        """Calculate precision: correct citations / predicted citations."""
        if not predicted_citations:
            return 0.0
        
        correct = len(set(predicted_citations) & set(expected_citations))
        return correct / len(predicted_citations)
    
    @staticmethod
    def calculate_recall(predicted_citations: List[str], expected_citations: List[str]) -> float:
        """Calculate recall: correct citations / expected citations."""
        if not expected_citations:
            return 1.0
        
        correct = len(set(predicted_citations) & set(expected_citations))
        return correct / len(expected_citations)
    
    @staticmethod
    def calculate_f1(precision: float, recall: float) -> float:
        """Calculate F1 score."""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)
    
    @staticmethod
    def calculate_answer_relevance(predicted_answer: str, expected_answer: str) -> float:
        """Calculate answer relevance using keyword overlap."""
        predicted_words = set(re.findall(r'\w+', predicted_answer.lower()))
        expected_words = set(re.findall(r'\w+', expected_answer.lower()))
        
        if not expected_words:
            return 0.0
        
        overlap = len(predicted_words & expected_words)
        return overlap / len(expected_words)
    
    @staticmethod
    def calculate_hallucination_rate(predicted_answer: str, context: str) -> float:
        """Estimate hallucination rate by checking if answer is grounded in context."""
        predicted_words = set(re.findall(r'\w+', predicted_answer.lower()))
        context_words = set(re.findall(r'\w+', context.lower()))
        
        if not predicted_words:
            return 0.0
        
        grounded_words = predicted_words & context_words
        return 1.0 - (len(grounded_words) / len(predicted_words))
