"""
Conversation history tracking for Company Brain Agent.
"""

from typing import List, Dict
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    citations: List[str] = field(default_factory=list)


class ConversationHistory:
    """Track conversation context."""
    
    def __init__(self, max_turns: int = 5):
        self.turns: List[ConversationTurn] = []
        self.max_turns = max_turns
    
    def add_user_message(self, content: str):
        """Add a user message to the history."""
        self.turns.append(ConversationTurn(role="user", content=content))
        self._trim_history()
    
    def add_assistant_message(self, content: str, citations: List[str] = None):
        """Add an assistant message to the history."""
        self.turns.append(ConversationTurn(
            role="assistant",
            content=content,
            citations=citations or []
        ))
        self._trim_history()
    
    def _trim_history(self):
        """Keep only the most recent turns."""
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
    
    def get_context_for_llm(self) -> List[Dict]:
        """Get conversation history formatted for LLM."""
        return [
            {"role": turn.role, "content": turn.content}
            for turn in self.turns
        ]
    
    def get_last_n_turns(self, n: int) -> List[ConversationTurn]:
        """Get the last n turns."""
        return self.turns[-n:]
    
    def clear(self):
        """Clear conversation history."""
        self.turns = []
    
    def get_citations(self) -> List[str]:
        """Get all citations from assistant messages."""
        citations = []
        for turn in self.turns:
            if turn.role == "assistant":
                citations.extend(turn.citations)
        return list(set(citations))  # Remove duplicates
