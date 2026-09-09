"""
Document loader for Company Brain MCP Server.
Loads documents from knowledge base directories.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import logging
from datetime import datetime

from config import (
    POLICIES_DIR, PRODUCT_DIR, ENGINEERING_DIR, 
    MEETINGS_DIR, INTERNAL_DIR
)

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a document in the knowledge base."""
    id: str
    title: str
    content: str
    category: str
    file_path: str
    metadata: Dict
    created_at: str
    updated_at: str
    source: str = "local"


class DocumentLoader:
    """Loads documents from knowledge base directories."""
    
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.category_dirs = {
            "policies": POLICIES_DIR,
            "product": PRODUCT_DIR,
            "engineering": ENGINEERING_DIR,
            "meetings": MEETINGS_DIR,
            "internal": INTERNAL_DIR
        }
    
    def load_all(self) -> List[Document]:
        """Load all documents from all categories."""
        all_docs = []
        for category, dir_path in self.category_dirs.items():
            docs = self.load_category(category, dir_path)
            all_docs.extend(docs)
        return all_docs
    
    def load_category(self, category: str, dir_path: Path) -> List[Document]:
        """Load documents from a specific category directory."""
        if not dir_path.exists():
            return []
        
        docs = []
        for file_path in dir_path.rglob("*.md"):
            doc = self._load_markdown(file_path, category)
            if doc:
                docs.append(doc)
                self.documents[doc.id] = doc
        
        for file_path in dir_path.rglob("*.txt"):
            doc = self._load_text(file_path, category)
            if doc:
                docs.append(doc)
                self.documents[doc.id] = doc
        
        for file_path in dir_path.rglob("*.json"):
            doc = self._load_json(file_path, category)
            if doc:
                docs.append(doc)
                self.documents[doc.id] = doc
        
        return docs
    
    def _load_markdown(self, file_path: Path, category: str) -> Optional[Document]:
        """Load a markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from first line if it starts with #
            title = file_path.stem
            lines = content.split('\n')
            if lines and lines[0].startswith('#'):
                title = lines[0].lstrip('#').strip()
            
            doc_id = f"{category}/{file_path.stem}"
            
            return Document(
                id=doc_id,
                title=title,
                content=content,
                category=category,
                file_path=str(file_path),
                metadata={"format": "markdown"},
                created_at=datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                updated_at=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            )
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def _load_text(self, file_path: Path, category: str) -> Optional[Document]:
        """Load a text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc_id = f"{category}/{file_path.stem}"
            
            return Document(
                id=doc_id,
                title=file_path.stem,
                content=content,
                category=category,
                file_path=str(file_path),
                metadata={"format": "text"},
                created_at=datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                updated_at=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            )
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def _load_json(self, file_path: Path, category: str) -> Optional[Document]:
        """Load a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(data, dict):
                title = data.get("title", file_path.stem)
                content = data.get("content", json.dumps(data, indent=2))
                metadata = {k: v for k, v in data.items() if k not in ["title", "content"]}
            else:
                title = file_path.stem
                content = json.dumps(data, indent=2)
                metadata = {"format": "json"}
            
            doc_id = f"{category}/{file_path.stem}"
            
            return Document(
                id=doc_id,
                title=title,
                content=content,
                category=category,
                file_path=str(file_path),
                metadata=metadata,
                created_at=datetime.fromtimestamp(file_path.stat().st_ctime).isoformat(),
                updated_at=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            )
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        return self.documents.get(doc_id)
    
    def get_documents_by_category(self, category: str) -> List[Document]:
        """Get all documents in a category."""
        return [doc for doc in self.documents.values() if doc.category == category]
    
    def search_by_title(self, query: str) -> List[Document]:
        """Search documents by title."""
        query_lower = query.lower()
        return [doc for doc in self.documents.values() if query_lower in doc.title.lower()]
