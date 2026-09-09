"""
GitHub connector for Company Brain.
Reads markdown/text files from a public GitHub repository via the raw content API.
Requires the repository to be public (or a token for private repos).
"""

import logging
from typing import List, Dict, Any
from datetime import datetime

import requests

from .base import BaseConnector, ConnectorDocument

logger = logging.getLogger(__name__)


class GitHubConnector(BaseConnector):
    """Connector that pulls markdown/text files from a GitHub repository tree."""

    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.owner = self.config.get("owner")
        self.repo = self.config.get("repo")
        self.branch = self.config.get("branch", "main")
        self.path = self.config.get("path", "").strip("/")
        self.category = self.config.get("category", "engineering")
        self.token = self.config.get("token") or self.config.get("github_token")

    def health_check(self) -> bool:
        return bool(self.owner and self.repo)

    def _api_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _api_url(self, endpoint: str) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{endpoint}?ref={self.branch}"

    def _raw_url(self, path: str) -> str:
        return f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/{path}"

    def fetch(self) -> List[ConnectorDocument]:
        if not self.health_check():
            return []

        docs = []
        try:
            items = self._list_tree(self.path)
            for item in items:
                if item.get("type") == "file" and item["name"].lower().endswith((".md", ".txt")):
                    doc = self._load_file(item["path"])
                    if doc:
                        docs.append(doc)
        except Exception as e:
            logger.error(f"GitHubConnector error: {e}")
        return docs

    def _list_tree(self, path: str) -> List[Dict[str, Any]]:
        url = self._api_url(path)
        response = requests.get(url, headers=self._api_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]

    def _load_file(self, path: str) -> Any:
        try:
            response = requests.get(self._raw_url(path), timeout=30)
            response.raise_for_status()
            content = response.text
            doc_id = f"{self.category}/{path.replace('/', '_').replace('.', '_')}"
            title = path.split("/")[-1].rsplit(".", 1)[0]
            now = datetime.now().isoformat()
            return ConnectorDocument(
                source_id=doc_id,
                title=title,
                content=content,
                category=self.category,
                file_path=f"github://{self.owner}/{self.repo}/{path}",
                metadata={"format": "markdown" if path.endswith(".md") else "text"},
                created_at=now,
                updated_at=now,
                source=self.name,
            )
        except Exception as e:
            logger.error(f"Error loading GitHub file {path}: {e}")
            return None
