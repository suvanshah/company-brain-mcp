"""
Base connector interface for Company Brain document sync.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class ConnectorDocument:
    """A document returned by a connector, before being converted to a server Document."""
    source_id: str
    title: str
    content: str
    category: str
    file_path: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    source: str = "unknown"


class BaseConnector(ABC):
    """Abstract base class for document connectors."""

    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def fetch(self) -> List[ConnectorDocument]:
        """Fetch all current documents from this source."""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Return True if the connector is configured and reachable."""
        return True
