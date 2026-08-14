"""
Ollama client for LLM calls in Company Brain Agent.
"""

import requests
import logging
from typing import List, Dict, Optional

from server.config import OLLAMA_BASE_URL, OLLAMA_LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama API."""
    
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model = model or OLLAMA_LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
    
    def generate(self, prompt: str, system_prompt: str = None, conversation_history: List[Dict] = None) -> str:
        """Generate a response from Ollama."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Ollama: {e}")
            return ""
    
    def generate_with_context(self, prompt: str, context: str, system_prompt: str = None) -> str:
        """Generate a response with provided context."""
        full_prompt = f"""Context:
{context}

Question:
{prompt}

Answer the question based on the context provided above. If the context doesn't contain the answer, say so explicitly."""
        
        return self.generate(full_prompt, system_prompt)
