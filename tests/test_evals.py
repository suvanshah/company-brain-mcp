"""
Evaluation and dataset validation tests for Company Brain MCP.

- Tests the deterministic citation metrics (precision/recall/F1).
- Tests the LLM-as-judge correctness scorer with a fake client.
- Validates that evals/questions.json is well-formed and that every expected
  citation file exists in knowledge/.

Run with: python -m unittest tests/test_evals.py
"""

import json
import os
import sys
import types
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_DIR = os.path.join(PROJECT_ROOT, "server")

# The server and project roots must be on sys.path for agent/server imports.
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Stub requests so that agent.ollama_client can be imported without installing
# the package in this environment. We never actually make network calls.
sys.modules["requests"] = types.SimpleNamespace(
    exceptions=types.SimpleNamespace(RequestException=Exception),
    post=lambda *a, **k: None,
)

from evals.metrics import EvaluationMetrics


class TestEvaluationMetrics(unittest.TestCase):
    def _metrics(self, judge_response: str = "Yes"):
        fake_client = types.SimpleNamespace(generate=lambda prompt: judge_response)
        return EvaluationMetrics(llm_client=fake_client)

    def test_perfect_citations_score_one(self):
        em = self._metrics()
        p = em.calculate_precision(["a", "b"], ["a", "b"])
        r = em.calculate_recall(["a", "b"], ["a", "b"])
        self.assertEqual(p, 1.0)
        self.assertEqual(r, 1.0)
        self.assertEqual(em.calculate_f1(p, r), 1.0)

    def test_partial_citations(self):
        em = self._metrics()
        p = em.calculate_precision(["a", "b", "c"], ["a", "b"])
        r = em.calculate_recall(["a", "b", "c"], ["a", "b"])
        self.assertAlmostEqual(p, 2.0 / 3.0)
        self.assertAlmostEqual(r, 1.0)

    def test_f1_handles_zero_precision_and_recall(self):
        em = self._metrics()
        self.assertEqual(em.calculate_f1(0.0, 0.0), 0.0)

    def test_citations_are_deduplicated(self):
        em = self._metrics()
        p = em.calculate_precision([{"id": "a"}, "a", {"id": "a"}], ["a"])
        self.assertEqual(p, 1.0)

    def test_correctness_yes(self):
        em = self._metrics("Yes, the predicted answer is correct.")
        self.assertEqual(em.calculate_correctness("q", "expected", "predicted"), 1.0)

    def test_correctness_no(self):
        em = self._metrics("No, the predicted answer is missing the key points.")
        self.assertEqual(em.calculate_correctness("q", "expected", "predicted"), 0.0)

    def test_correctness_no_keyword_yes_first_token(self):
        em = self._metrics("Correct")
        self.assertEqual(em.calculate_correctness("q", "expected", "predicted"), 0.0)


class TestQuestionsDataset(unittest.TestCase):
    def test_questions_json_is_valid(self):
        questions_path = Path(PROJECT_ROOT) / "evals" / "questions.json"
        with open(questions_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("test_questions", data)
        self.assertTrue(isinstance(data["test_questions"], list))

    def test_expected_citations_exist(self):
        questions_path = Path(PROJECT_ROOT) / "evals" / "questions.json"
        with open(questions_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for question in data["test_questions"]:
            for field in ("id", "query", "expected_answer", "expected_citations", "category"):
                self.assertIn(field, question, f"Question {question.get('id')} missing {field}")

            for citation in question["expected_citations"]:
                self.assertIn("/", citation)
                category, stem = citation.split("/", 1)
                candidate = Path(PROJECT_ROOT) / "knowledge" / category / f"{stem}.md"
                self.assertTrue(
                    candidate.exists(),
                    f"Missing expected citation file for {citation}: {candidate}",
                )


if __name__ == "__main__":
    unittest.main()
