"""
Citation formatter for Company Brain Agent.
Formats citations from retrieved documents.
"""

from typing import List, Dict


class CitationFormatter:
    """Format citations for document references."""
    
    @staticmethod
    def format_citations(citations: List[str], documents: Dict[str, Dict]) -> str:
        """Format citations as a list of references."""
        if not citations:
            return ""
        
        formatted = "\n\n**Sources:**\n"
        for i, citation in enumerate(citations, 1):
            doc = documents.get(citation, {})
            title = doc.get("title", citation)
            category = doc.get("category", "unknown")
            formatted += f"{i}. {title} ({category})\n"
        
        return formatted
    
    @staticmethod
    def format_inline_citation(citation: str, documents: Dict[str, Dict]) -> str:
        """Format a single inline citation."""
        doc = documents.get(citation, {})
        title = doc.get("title", citation)
        return f"[{title}]"
    
    @staticmethod
    def extract_citations_from_text(text: str) -> List[str]:
        """Extract citation IDs from text (e.g., [policies/ai_deployment_policy])."""
        import re
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, text)
        return matches
