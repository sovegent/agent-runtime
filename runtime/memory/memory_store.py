"""
Persistent memory store for Agent Runtime.

Replaces the in-memory stub with JSON-backed persistence.
Each session gets its own file. Agents can recall history across runs.

This is what separates a stateless chatbot from a stateful agent.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryStore:
    def __init__(
        self,
        session_id: str,
        storage_path: str = "./data/memory",
        persist: bool = True,
    ):
        self.session_id = session_id
        self.persist = persist
        self.storage_path = Path(storage_path)
        self._entries: List[Dict] = []

        if self.persist:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._load()

    @property
    def _file_path(self) -> Path:
        return self.storage_path / f"{self.session_id}.json"

    def _load(self):
        if self._file_path.exists():
            try:
                with open(self._file_path) as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._entries = []

    def _flush(self):
        if not self.persist:
            return
        with open(self._file_path, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    def save(self, data: Dict[str, Any]) -> str:
        """Save an entry to memory. Returns the entry ID."""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            **data,
        }
        self._entries.append(entry)
        self._flush()
        return entry["id"]

    def get_all(self) -> List[Dict]:
        """Return all memory entries for this session."""
        return list(self._entries)

    def get_recent(self, n: int = 10) -> List[Dict]:
        """Return the N most recent memory entries."""
        return self._entries[-n:]

    def get_steps(self) -> List[Dict]:
        """Return only step entries (tool calls and results)."""
        return [e for e in self._entries if e.get("type") == "step"]

    def search(self, query: str) -> List[Dict]:
        """Simple full-text search across all memory entries."""
        q = query.lower()
        return [
            entry for entry in self._entries
            if q in json.dumps(entry, default=str).lower()
        ]

    def clear(self):
        """Clear all entries for this session."""
        self._entries = []
        self._flush()

    # Legacy API compatibility
    def save_legacy(self, data):
        return self.save({"data": data})

    def summary(self) -> Dict:
        return {
            "session_id": self.session_id,
            "entry_count": len(self._entries),
            "step_count": len(self.get_steps()),
            "persisted": self.persist,
            "file": str(self._file_path) if self.persist else None,
        }
