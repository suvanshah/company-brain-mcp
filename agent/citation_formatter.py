"""
Citation formatter for Company Brain Agent.
Formats citations from retrieved documents.
"""

from typing import List, Dict, Any


class CitationFormatter:
    """Format citations for document references."""
    
    @staticmethod
    def _citation_parts(citation: Any, documents: Dict[str, Dict]) -> Dict[str, str]:
        """Extract title, category, section from a citation entry."""
        if isinstance(citation, dict):
            return {
                "title": citation.get("title", citation.get("id", "unknown")),
                "category": citation.get("category", "unknown"),
                "section": citation.get("section"),
            }
        # Legacy string citation: look up the document.
        doc = documents.get(citation, {})
        return {
            "title": doc.get("title", citation),
            "category": doc.get("category", "unknown"),
            "section": doc.get("section"),
        }

    @staticmethod
    def format_citations(citations: List[Any], documents: Dict[str, Dict]) -> str:
        """Format citations as a list of references."""
        if not citations:
            return ""
        
        formatted = "\n\n**Sources:**\n"
        for i, citation in enumerate(citations, 1):
            parts = CitationFormatter._citation_parts(citation, documents)
            title = parts["title"]
            category = parts["category"]
            section = parts["section"]
            label = title
            if section:
                label = f"{title} — {section}"
            formatted += f"{i}. {label} ({category})\n"
        
        return formatted
    
    @staticmethod
    def format_inline_citation(citation: Any, documents: Dict[str, Dict]) -> str:
        """Format a single inline citation."""
        parts = CitationFormatter._citation_parts(citation, documents)
        return f"[{parts['title']}]"
    
    @staticmethod
    def extract_citations_from_text(text: str) -> List[str]:
        """Extract citation IDs from text (e.g., [policies/ai_deployment_policy])."""
        import re
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, text)
        return matches
