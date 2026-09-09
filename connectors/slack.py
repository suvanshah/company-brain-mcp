"""
Slack export connector for Company Brain.
Reads a Slack export zip file and yields one Document per channel/day.
"""

import json
import logging
import zipfile
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .base import BaseConnector, ConnectorDocument

logger = logging.getLogger(__name__)


class SlackExportConnector(BaseConnector):
    """Connector that reads a Slack export zip archive."""

    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.export_path = Path(self.config.get("export_path", "")).expanduser()
        self.category = self.config.get("category", "meetings")

    def health_check(self) -> bool:
        return self.export_path.exists() and self.export_path.suffix == ".zip"

    def fetch(self) -> List[ConnectorDocument]:
        if not self.health_check():
            logger.error(f"SlackExportConnector: invalid export file {self.export_path}")
            return []

        docs = []
        try:
            with zipfile.ZipFile(self.export_path, "r") as zf:
                json_files = [n for n in zf.namelist() if n.endswith(".json") and "/" in n]
                for name in json_files:
                    content = self._read_day_messages(zf, name)
                    if content:
                        docs.append(content)
        except Exception as e:
            logger.error(f"SlackExportConnector error: {e}")
        return docs

    def _read_day_messages(self, zf: zipfile.ZipFile, name: str) -> Any:
        try:
            data = json.loads(zf.read(name))
            if not isinstance(data, list) or not data:
                return None

            parts = name.split("/")
            channel = parts[-2] if len(parts) >= 2 else "unknown"
            day = parts[-1].replace(".json", "")

            messages = []
            for msg in data:
                if not isinstance(msg, dict):
                    continue
                text = msg.get("text", "").strip()
                user = msg.get("user") or msg.get("user_profile", {}).get("display_name", "unknown")
                ts = msg.get("ts", "")
                if text:
                    messages.append(f"[{ts}] {user}: {text}")

            if not messages:
                return None

            content = f"# Slack #{channel} - {day}\n\n" + "\n\n".join(messages)
            doc_id = f"{self.category}/{channel}_{day}"
            now = datetime.now().isoformat()
            return ConnectorDocument(
                source_id=doc_id,
                title=f"Slack #{channel} - {day}",
                content=content,
                category=self.category,
                file_path=f"slack://{self.export_path.name}/{name}",
                metadata={"format": "slack", "channel": channel, "day": day},
                created_at=now,
                updated_at=now,
                source=self.name,
            )
        except Exception as e:
            logger.error(f"Error reading Slack export file {name}: {e}")
            return None
