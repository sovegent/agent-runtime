"""
Semantic memory — recall by meaning, not just keywords.

Upgrades the base MemoryStore with full-text search using SQLite FTS5.
FTS5 is built into Python's sqlite3 — zero extra dependencies.

Why this matters:
  Base MemoryStore: linear scan, exact keyword match
  SemanticMemory:   ranked full-text search, stemming, relevance scoring

Upgrade path to true vector embeddings:
  Set embedding_fn to any function that takes a string and returns
  a list of floats. Works with OpenAI embeddings, Anthropic,
  sentence-transformers, or any local model.

Usage:
  mem = SemanticMemory(session_id="abc123")
  mem.save({"type": "step", "content": "nginx returned 502 on /api/health"})
  results = mem.search("server health check error")
  # Returns ranked results — most relevant first
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class SemanticMemory:
    """
    Drop-in upgrade for MemoryStore with ranked full-text search.

    Stores all entries in SQLite with FTS5 indexing.
    Optionally stores embeddings for true semantic similarity.
    """

    def __init__(
        self,
        session_id: str,
        storage_path: str = "./data/memory",
        persist: bool = True,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        top_k: int = 10,
    ):
        self.session_id = session_id
        self.persist = persist
        self.embedding_fn = embedding_fn
        self.top_k = top_k

        storage = Path(storage_path)
        storage.mkdir(parents=True, exist_ok=True)

        db_path = str(storage / f"{session_id}.db") if persist else ":memory:"
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._setup_schema()

    def _setup_schema(self):
        c = self._conn.cursor()

        # Main entries table
        c.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                type        TEXT,
                role        TEXT,
                content     TEXT,
                step        INTEGER,
                tool        TEXT,
                data_json   TEXT,
                embedding   TEXT
            )
        """)

        # Standalone FTS5 table — stores searchable text directly.
        # Using porter stemmer for better recall (disk/disks/disk's all match).
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts
            USING fts5(entry_id, searchable_text, tokenize='porter ascii')
        """)

        self._conn.commit()

    def _entry_to_dict(self, row) -> Dict:
        d = dict(row)
        if d.get("data_json"):
            try:
                extra = json.loads(d["data_json"])
                d.update(extra)
            except Exception:
                pass
            del d["data_json"]
        d.pop("embedding", None)
        return {k: v for k, v in d.items() if v is not None}

    def _make_searchable(self, data: Dict) -> str:
        """Flatten a data dict into a single searchable string."""
        parts = []
        for v in data.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, dict):
                parts.append(json.dumps(v, default=str))
            elif v is not None:
                parts.append(str(v))
        return " ".join(parts)

    def save(self, data: Dict[str, Any]) -> str:
        """Save an entry. Returns the entry ID."""
        entry_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        known = {"type", "role", "content", "step", "tool"}
        extra = {k: v for k, v in data.items() if k not in known}
        data_json = json.dumps(extra, default=str) if extra else None

        searchable = self._make_searchable(data)

        embedding_json = None
        if self.embedding_fn:
            try:
                vec = self.embedding_fn(searchable)
                embedding_json = json.dumps(vec)
            except Exception:
                pass

        c = self._conn.cursor()
        c.execute("""
            INSERT INTO entries
              (id, session_id, timestamp, type, role, content, step, tool, data_json, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, self.session_id, now,
            data.get("type"), data.get("role"), searchable,
            data.get("step"), data.get("tool"),
            data_json, embedding_json,
        ))

        # Also insert into FTS index
        c.execute(
            "INSERT INTO entries_fts(entry_id, searchable_text) VALUES (?, ?)",
            (entry_id, searchable)
        )

        self._conn.commit()
        return entry_id

    def _build_fts_query(self, query: str) -> str:
        """
        Convert a natural language query into an FTS5 MATCH expression.

        FTS5 treats spaces as AND (all words must appear). For recall-oriented
        search we want OR semantics with prefix wildcards so partial words match.

        "web server port" → "web* OR server* OR port*"

        Strips FTS5 special chars to avoid syntax errors from raw user input.
        """
        # Strip FTS5 operators/special chars that could cause syntax errors
        import re
        clean = re.sub(r'["\'\(\)\^\*\:\-]', ' ', query)
        words = [w.strip() for w in clean.split() if len(w.strip()) > 1]
        if not words:
            return query
        # Each word gets a prefix wildcard; joined with OR for broad recall
        return " OR ".join(f"{w}*" for w in words)

    def search(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        """
        Full-text search across all memory entries.
        Returns results ranked by FTS5 relevance (most relevant first).

        Multi-word queries use OR + prefix matching for maximum recall.
        If embedding_fn is set, results are reranked by cosine similarity.
        """
        k = top_k or self.top_k
        c = self._conn.cursor()
        fts_query = self._build_fts_query(query)

        try:
            c.execute("""
                SELECT e.*
                FROM entries e
                JOIN entries_fts fts ON e.id = fts.entry_id
                WHERE fts.searchable_text MATCH ?
                  AND e.session_id = ?
                ORDER BY rank
                LIMIT ?
            """, (fts_query, self.session_id, k * 2))
            rows = c.fetchall()
        except sqlite3.OperationalError:
            # Last resort: LIKE scan
            c.execute("""
                SELECT * FROM entries
                WHERE session_id = ? AND content LIKE ?
                LIMIT ?
            """, (self.session_id, f"%{query}%", k))
            rows = c.fetchall()

        results = [self._entry_to_dict(r) for r in rows]

        if self.embedding_fn and results:
            results = self._rerank_by_embedding(query, results, k)

        return results[:k]

    def _rerank_by_embedding(self, query: str, results: List[Dict], k: int) -> List[Dict]:
        try:
            import math

            def cosine(a, b):
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(x * x for x in b))
                return dot / (na * nb + 1e-9)

            q_vec = self.embedding_fn(query)
            c = self._conn.cursor()
            for r in results:
                c.execute("SELECT embedding FROM entries WHERE id=?", (r.get("id"),))
                row = c.fetchone()
                r["_score"] = cosine(q_vec, json.loads(row[0])) if row and row[0] else 0.0

            results.sort(key=lambda x: x["_score"], reverse=True)
            for r in results:
                r.pop("_score", None)
        except Exception:
            pass
        return results

    def get_all(self) -> List[Dict]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM entries WHERE session_id=? ORDER BY timestamp", (self.session_id,))
        return [self._entry_to_dict(r) for r in c.fetchall()]

    def get_recent(self, n: int = 10) -> List[Dict]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM entries WHERE session_id=? ORDER BY timestamp DESC LIMIT ?", (self.session_id, n))
        return list(reversed([self._entry_to_dict(r) for r in c.fetchall()]))

    def get_steps(self) -> List[Dict]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM entries WHERE session_id=? AND type='step' ORDER BY timestamp", (self.session_id,))
        return [self._entry_to_dict(r) for r in c.fetchall()]

    def clear(self):
        c = self._conn.cursor()
        ids = [r[0] for r in c.execute("SELECT id FROM entries WHERE session_id=?", (self.session_id,)).fetchall()]
        c.execute("DELETE FROM entries WHERE session_id=?", (self.session_id,))
        for eid in ids:
            c.execute("DELETE FROM entries_fts WHERE entry_id=?", (eid,))
        self._conn.commit()

    def summary(self) -> Dict:
        c = self._conn.cursor()
        total = c.execute("SELECT COUNT(*) FROM entries WHERE session_id=?", (self.session_id,)).fetchone()[0]
        steps = c.execute("SELECT COUNT(*) FROM entries WHERE session_id=? AND type='step'", (self.session_id,)).fetchone()[0]
        return {
            "session_id": self.session_id,
            "entry_count": total,
            "step_count": steps,
            "persisted": self.persist,
            "backend": "sqlite_fts5",
            "has_embeddings": self.embedding_fn is not None,
        }

    def close(self):
        self._conn.close()
