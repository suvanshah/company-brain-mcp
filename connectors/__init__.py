"""
Connectors for syncing company documents into Company Brain.
"""

from .base import BaseConnector, ConnectorDocument
from .filesystem import FilesystemConnector
from .sync_manager import SyncManager

try:
    from .github import GitHubConnector
except ImportError:
    GitHubConnector = None  # type: ignore

try:
    from .slack import SlackExportConnector
except ImportError:
    SlackExportConnector = None  # type: ignore

__all__ = [
    "BaseConnector",
    "ConnectorDocument",
    "FilesystemConnector",
    "SyncManager",
    "GitHubConnector",
    "SlackExportConnector",
]
