"""
Session manager for Agent Runtime.

Tracks agent sessions across runs so you can resume, review,
and build state over time.
"""

import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional


class SessionManager:
    def __init__(self, storage_path: str = "./data/sessions"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._index_file = self.storage_path / "index.json"
        self._sessions: Dict = self._load_index()

    def _load_index(self) -> Dict:
        if self._index_file.exists():
            try:
                with open(self._index_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_index(self):
        with open(self._index_file, "w") as f:
            json.dump(self._sessions, f, indent=2, default=str)

    def create_session(self, label: Optional[str] = None, agent: Optional[str] = None) -> str:
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        self._sessions[session_id] = {
            "id": session_id,
            "label": label or f"session-{session_id}",
            "agent": agent or "unknown",
            "created_at": now,
            "updated_at": now,
            "step_count": 0,
        }
        self._save_index()
        return session_id

    def update_session(self, session_id: str, **kwargs):
        if session_id in self._sessions:
            self._sessions[session_id].update(kwargs)
            self._sessions[session_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_index()

    def get_session(self, session_id: str) -> Optional[Dict]:
        return self._sessions.get(session_id)

    def list_sessions(self, n: int = 20) -> List[Dict]:
        sessions = list(self._sessions.values())
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)[:n]

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions
