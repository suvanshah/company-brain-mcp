"""
Filesystem connector for Company Brain.
Watches a local directory and yields documents for supported files.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .base import BaseConnector, ConnectorDocument

logger = logging.getLogger(__name__)


class FilesystemConnector(BaseConnector):
    """Connector that reads documents from a local directory tree."""

    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.root = Path(self.config.get("root", ".")).expanduser().resolve()
        self.category = self.config.get("category")
        self.extensions = tuple(self.config.get("extensions", [".md", ".txt", ".json"]))

    def health_check(self) -> bool:
        return self.root.exists() and self.root.is_dir()

    def fetch(self) -> List[ConnectorDocument]:
        """Fetch all documents under the configured root directory."""
        if not self.health_check():
            logger.error(f"FilesystemConnector root does not exist: {self.root}")
            return []

        docs = []
        for file_path in self.root.rglob("*"):
            if not file_path.is_file() or not file_path.name.endswith(self.extensions):
                continue
            doc = self._load_file(file_path)
            if doc:
                docs.append(doc)
        return docs

    def _load_file(self, file_path: Path) -> Optional[ConnectorDocument]:
        try:
            content = file_path.read_text(encoding="utf-8")
            suffix = file_path.suffix.lower()
            stat = file_path.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
            updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()

            # Derive category from the immediate parent directory name if not configured
            category = self.category
            if not category:
                try:
                    category = file_path.relative_to(self.root).parts[0]
                except IndexError:
                    category = "general"

            doc_id = f"{category}/{file_path.stem}"

            if suffix == ".md":
                title = file_path.stem
                lines = content.split("\n")
                if lines and lines[0].startswith("#"):
                    title = lines[0].lstrip("#").strip()
                metadata = {"format": "markdown"}
            elif suffix == ".json":
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = {}
                if isinstance(data, dict):
                    title = data.get("title", file_path.stem)
                    content = data.get("content", json.dumps(data, indent=2))
                    metadata = {k: v for k, v in data.items() if k not in ["title", "content"]}
                else:
                    title = file_path.stem
                    metadata = {"format": "json"}
            else:
                title = file_path.stem
                metadata = {"format": "text"}

            return ConnectorDocument(
                source_id=doc_id,
                title=title,
                content=content,
                category=category,
                file_path=str(file_path),
                metadata=metadata,
                created_at=created_at,
                updated_at=updated_at,
                source=self.name,
            )
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
