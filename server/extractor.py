"""
Triple extractor for Company Brain.
Uses a local Ollama model to turn free text into subject-predicate-object triples.
"""

import json
import logging
from typing import List, Dict

import requests

from config import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """Extract the meaningful entities, decisions, commitments, and relationships from the following company document.

Return a JSON object with a single key "triples" containing a list of objects. Each object must have:
- "subject": the entity the statement is about (person, project, decision, commitment, blocker, topic, policy)
- "predicate": the relationship (e.g. requires, decided_by, committed_to, blocks, depends_on, objected_by, proposed, includes, owns, deadline, status, approved, rationale, reason)
- "object": the related entity or value
- "confidence": a number from 0.0 to 1.0

Important:
- For every decision, also extract the RATIONALE. Use predicate "rationale" and the object should be the reason or justification stated in the text.
- For every decision, also extract who PROPOSED it, who DECIDED it, and who OBJECTED (use predicates proposed_by, decided_by, objected_by).
- Only extract clear, fact-like claims. Do not infer things that are not in the text.

Example output:
{
  "triples": [
    {"subject": "AI deployment policy", "predicate": "requires", "object": "executive sign-off", "confidence": 0.95},
    {"subject": "Q4 2024", "predicate": "includes", "object": "enterprise features", "confidence": 0.95},
    {"subject": "Alice", "predicate": "committed_to", "object": "deliver mobile app MVP by July 15", "confidence": 0.9},
    {"subject": "OAuth 2.0 implementation", "predicate": "rationale", "object": "improve security and simplify customer integrations", "confidence": 0.9},
    {"subject": "authentication decision", "predicate": "decided_by", "object": "Security team", "confidence": 0.9}
  ]
}
"""


class TripleExtractor:
    """Extracts subject-predicate-object triples from text using Ollama."""

    def __init__(self, model: str = None, base_url: str = None, timeout: int = 60):
        self.model = model or OLLAMA_LLM_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL
        self.timeout = timeout

    def extract(self, text: str) -> List[Dict]:
        """Return a list of triples extracted from the text."""
        if not text.strip():
            return []

        payload = {
            "model": self.model,
            "prompt": text,
            "system": EXTRACTION_PROMPT,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Ollama extraction call failed: {e}")
            return []

        data = response.json()
        raw = data.get("response", "")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Extractor returned non-JSON response: {raw!r}")
            return []

        triples = parsed.get("triples", [])
        if not isinstance(triples, list):
            logger.warning(f"Extractor JSON did not contain a 'triples' list: {parsed!r}")
            return []

        # Normalize: ensure all triples have the required keys
        valid = []
        for t in triples:
            if isinstance(t, dict) and "subject" in t and "predicate" in t and "object" in t:
                valid.append({
                    "subject": str(t["subject"]),
                    "predicate": str(t["predicate"]),
                    "object": str(t["object"]),
                    "confidence": float(t.get("confidence", 0.8)),
                })
        return valid
