"""
SyncManager aggregates documents from all configured connectors and maintains
a persistent state file to detect new/changed/deleted documents.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from .base import BaseConnector, ConnectorDocument
from document_loader import Document

logger = logging.getLogger(__name__)


def _content_hash(content: str) -> str:
    return hashlib.md5(content.encode("utf-8")).hexdigest()


class SyncManager:
    """Orchestrates document connectors and produces a canonical document set."""

    def __init__(self, state_path: Path = None):
        self.connectors: List[BaseConnector] = []
        self.state_path = state_path or (Path(__file__).resolve().parent.parent / "data" / "sync_state.json")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def add_connector(self, connector: BaseConnector):
        """Register a document source."""
        self.connectors.append(connector)

    def _load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load sync state: {e}")
        return {}

    def _save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save sync state: {e}")

    def _to_document(self, cd: ConnectorDocument) -> Document:
        return Document(
            id=cd.source_id,
            title=cd.title,
            content=cd.content,
            category=cd.category,
            file_path=cd.file_path,
            metadata={**cd.metadata, "source": cd.source},
            created_at=cd.created_at,
            updated_at=cd.updated_at,
            source=cd.source,
        )

    def sync(self) -> List[Document]:
        """Fetch documents from all connectors, detect changes, and return the current set."""
        all_connector_docs: List[ConnectorDocument] = []
        for connector in self.connectors:
            if not connector.health_check():
                logger.warning(f"Connector {connector.name} failed health check; skipping")
                continue
            logger.info(f"Syncing connector: {connector.name}")
            docs = connector.fetch()
            logger.info(f"  {connector.name}: fetched {len(docs)} documents")
            all_connector_docs.extend(docs)

        documents = [self._to_document(cd) for cd in all_connector_docs]

        # Update state: map doc id to content hash and source
        new_state = {
            doc.id: {"hash": _content_hash(doc.content), "updated_at": doc.updated_at, "source": doc.source}
            for doc in documents
        }
        self._state = new_state
        self._save_state()

        return documents

    def get_changed_doc_ids(self, documents: List[Document]) -> List[str]:
        """Return IDs of documents that are new or changed compared to the last sync state."""
        changed = []
        for doc in documents:
            doc_hash = _content_hash(doc.content)
            previous = self._state.get(doc.id, {})
            if previous.get("hash") != doc_hash:
                changed.append(doc.id)
        return changed
