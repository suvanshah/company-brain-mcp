"""
MCP tools for Company Brain Server.
Implements search_documents(), read_document(), list_policies(), find_meeting_notes().
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

from document_loader import DocumentLoader, Document
from permissions import PermissionManager, Role
from embeddings import EmbeddingSearch, SearchResult


@dataclass
class ToolResult:
    """Result from an MCP tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    citations: List[str] = None


class MCPTools:
    """MCP tools for document access and search."""
    
    def __init__(self, document_loader: DocumentLoader, permission_manager: PermissionManager, embedding_search: EmbeddingSearch = None):
        self.loader = document_loader
        self.permissions = permission_manager
        self.embedding_search = embedding_search
    
    def list_policies(self, role: Role = Role.GUEST) -> ToolResult:
        """List all policy documents."""
        if not self.permissions.can_list_category(role, "policies"):
            return ToolResult(
                success=False,
                data=None,
                error="Permission denied: Cannot list policies"
            )
        
        policies = self.loader.get_documents_by_category("policies")
        policy_list = [
            {
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "updated_at": doc.updated_at
            }
            for doc in policies
        ]
        
        return ToolResult(
            success=True,
            data=policy_list,
            citations=[doc.id for doc in policies]
        )
    
    def read_document(self, doc_id: str, role: Role = Role.GUEST) -> ToolResult:
        """Read a specific document by ID."""
        doc = self.loader.get_document(doc_id)
        
        if not doc:
            return ToolResult(
                success=False,
                data=None,
                error=f"Document not found: {doc_id}"
            )
        
        if not self.permissions.can_read_document(role, doc.category):
            return ToolResult(
                success=False,
                data=None,
                error=f"Permission denied: Cannot access {doc.category} documents"
            )
        
        return ToolResult(
            success=True,
            data={
                "id": doc.id,
                "title": doc.title,
                "content": doc.content,
                "category": doc.category,
                "metadata": doc.metadata,
                "updated_at": doc.updated_at
            },
            citations=[doc_id]
        )
    
    def search_documents(self, query: str, role: Role = Role.GUEST, category: Optional[str] = None) -> ToolResult:
        """Search documents by query using semantic search."""
        accessible_categories = self.permissions.get_accessible_categories(role)
        
        if category:
            if category not in accessible_categories:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Permission denied: Cannot search {category}"
                )
            categories_to_search = [category]
        else:
            categories_to_search = list(accessible_categories)
        
        # Use semantic search if available, otherwise fall back to text search
        if self.embedding_search:
            results = []
            for cat in categories_to_search:
                search_results = self.embedding_search.search(query, top_k=5, category=cat)
                for result in search_results:
                    results.append({
                        "id": result.document.id,
                        "title": result.document.title,
                        "category": result.document.category,
                        "snippet": result.snippet,
                        "score": result.score,
                        "updated_at": result.document.updated_at
                    })
        else:
            # Fallback to simple text search
            results = []
            for cat in categories_to_search:
                docs = self.loader.get_documents_by_category(cat)
                for doc in docs:
                    if query.lower() in doc.title.lower() or query.lower() in doc.content.lower():
                        results.append({
                            "id": doc.id,
                            "title": doc.title,
                            "category": doc.category,
                            "snippet": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                            "score": 0.0,
                            "updated_at": doc.updated_at
                        })
        
        return ToolResult(
            success=True,
            data=results,
            citations=[r["id"] for r in results]
        )
    
    def find_meeting_notes(self, query: str, role: Role = Role.GUEST) -> ToolResult:
        """Find meeting notes matching a query."""
        if not self.permissions.can_search_category(role, "meetings"):
            return ToolResult(
                success=False,
                data=None,
                error="Permission denied: Cannot search meeting notes"
            )
        
        meetings = self.loader.get_documents_by_category("meetings")
        results = []
        
        for doc in meetings:
            if query.lower() in doc.title.lower() or query.lower() in doc.content.lower():
                results.append({
                    "id": doc.id,
                    "title": doc.title,
                    "date": doc.metadata.get("date", "unknown"),
                    "snippet": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                })
        
        return ToolResult(
            success=True,
            data=results,
            citations=[r["id"] for r in results]
        )
    
    def list_categories(self, role: Role = Role.GUEST) -> ToolResult:
        """List all accessible categories for a role."""
        categories = self.permissions.get_accessible_categories(role)
        
        category_info = []
        for cat in categories:
            docs = self.loader.get_documents_by_category(cat)
            category_info.append({
                "category": cat,
                "document_count": len(docs)
            })
        
        return ToolResult(
            success=True,
            data=category_info
        )
