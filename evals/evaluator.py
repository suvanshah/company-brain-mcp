"""
Evaluator for Company Brain Agent.
Runs evaluations and scores accuracy.
"""

import json
import logging
from typing import Dict, List
from datetime import datetime

import anyio

from agent.assistant import CompanyBrainAssistant
from evals.metrics import EvaluationMetrics

logger = logging.getLogger(__name__)


class Evaluator:
    """Evaluate agent performance on test questions."""

    def __init__(self, questions_file: str = "evals/questions.json"):
        self.questions_file = questions_file
        self.metrics = EvaluationMetrics()
        self.results = []

    def load_questions(self) -> List[Dict]:
        """Load test questions from JSON file."""
        with open(self.questions_file, 'r') as f:
            data = json.load(f)
        return data["test_questions"]

    async def run_evaluation(self) -> Dict:
        """Run evaluation on all test questions."""
        logger.info("Starting evaluation...")

        questions = self.load_questions()
        async with CompanyBrainAssistant() as assistant:
            return await self._evaluate(assistant, questions)

    async def _evaluate(self, assistant: CompanyBrainAssistant, questions: List[Dict]) -> Dict:
        total_precision = 0
        total_recall = 0
        total_f1 = 0
        total_correctness = 0

        for question in questions:
            logger.info(f"Evaluating question: {question['id']}")

            answer = await assistant.answer_question(question["query"])
            predicted_citations = assistant.get_last_citations()
            expected_citations = question["expected_citations"]

            precision = self.metrics.calculate_precision(predicted_citations, expected_citations)
            recall = self.metrics.calculate_recall(predicted_citations, expected_citations)
            f1 = self.metrics.calculate_f1(precision, recall)
            correctness = self.metrics.calculate_correctness(
                question["query"], question["expected_answer"], answer
            )

            result = {
                "question_id": question["id"],
                "query": question["query"],
                "predicted_answer": answer,
                "expected_answer": question["expected_answer"],
                "predicted_citations": predicted_citations,
                "expected_citations": expected_citations,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "correctness": correctness,
                "category": question["category"]
            }
            self.results.append(result)

            total_precision += precision
            total_recall += recall
            total_f1 += f1
            total_correctness += correctness

            logger.info(f"  P: {precision:.2f}, R: {recall:.2f}, F1: {f1:.2f}, Correct: {correctness:.2f}")

        num_questions = len(questions)
        avg_metrics = {
            "avg_precision": total_precision / num_questions,
            "avg_recall": total_recall / num_questions,
            "avg_f1": total_f1 / num_questions,
            "avg_correctness": total_correctness / num_questions,
            "num_questions": num_questions,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"Evaluation complete. Average F1: {avg_metrics['avg_f1']:.2f}, Correctness: {avg_metrics['avg_correctness']:.2f}")

        return avg_metrics

    def save_results(self, output_file: str = "evals/results.json"):
        """Save evaluation results to JSON file."""
        with open(output_file, 'w') as f:
            json.dump({
                "summary": self._calculate_summary(),
                "detailed_results": self.results
            }, f, indent=2)
        logger.info(f"Results saved to {output_file}")

    def _calculate_summary(self) -> Dict:
        """Calculate summary statistics from results."""
        if not self.results:
            return {}

        num_questions = len(self.results)
        avg_precision = sum(r["precision"] for r in self.results) / num_questions
        avg_recall = sum(r["recall"] for r in self.results) / num_questions
        avg_f1 = sum(r["f1"] for r in self.results) / num_questions
        avg_correctness = sum(r["correctness"] for r in self.results) / num_questions

        return {
            "num_questions": num_questions,
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_f1": avg_f1,
            "avg_correctness": avg_correctness,
            "timestamp": datetime.now().isoformat()
        }

    def print_summary(self):
        """Print evaluation summary."""
        summary = self._calculate_summary()

        print("\n" + "=" * 60)
        print("EVALUATION SUMMARY")
        print("=" * 60)
        print(f"Questions evaluated: {summary['num_questions']}")
        print(f"Average Precision: {summary['avg_precision']:.2f}")
        print(f"Average Recall: {summary['avg_recall']:.2f}")
        print(f"Average F1: {summary['avg_f1']:.2f}")
        print(f"Average Correctness: {summary['avg_correctness']:.2f}")
        print("=" * 60)


async def main():
    """Main entry point for evaluation."""
    import sys
    
    evaluator = Evaluator()
    
    print("Running Company Brain Agent Evaluation...")
    print("-" * 60)
    
    try:
        await evaluator.run_evaluation()
        evaluator.print_summary()
        evaluator.save_results()
        
        print("\nDetailed results saved to evals/results.json")
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
