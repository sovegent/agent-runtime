"""
examples/semantic_memory_demo.py

Demonstrates semantic memory — recall by meaning, not keywords.

Saves a batch of entries (server events, findings, notes),
then searches for related content using natural language.

The search uses SQLite FTS5 for ranked full-text retrieval.
Plug in an embedding function for true semantic similarity.

Run:
  python examples/semantic_memory_demo.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.memory.semantic_memory import SemanticMemory


def main():
    mem = SemanticMemory(
        session_id="demo-semantic",
        storage_path="./data/memory",
        persist=True,
    )
    mem.clear()

    # Seed with diverse entries an agent might have written
    entries = [
        {"type": "step", "tool": "shell", "content": "nginx status: active (running) since Mon. Serving 1204 req/s"},
        {"type": "step", "tool": "shell", "content": "disk usage: /var/log is 87% full. 14GB used, 2GB remaining"},
        {"type": "step", "tool": "shell", "content": "memory: 6.2GB used of 8GB, swap 0 used. Load average 0.4 0.6 0.7"},
        {"type": "step", "tool": "ssh",   "content": "failed login attempts: 47 in last hour from 103.21.x.x"},
        {"type": "step", "tool": "http",  "content": "health endpoint /api/health returned 200 OK in 43ms"},
        {"type": "step", "tool": "file",  "content": "wrote disk cleanup report: removed 8 log files totalling 3.2GB"},
        {"type": "note",                  "content": "production database backup completed successfully at 03:00 UTC"},
        {"type": "note",                  "content": "SSL certificate expires in 14 days — renewal needed"},
        {"type": "step", "tool": "shell", "content": "docker ps: 4 containers running. api, worker, redis, postgres all healthy"},
        {"type": "step", "tool": "shell", "content": "top processes: python 34% CPU, postgres 12%, nginx 2%"},
    ]

    print(f"Saving {len(entries)} memory entries...\n")
    for e in entries:
        mem.save(e)

    queries = [
        "disk space problems",
        "security intrusion attempts",
        "web server performance",
        "database status",
        "certificate expiry",
    ]

    for query in queries:
        results = mem.search(query, top_k=2)
        print(f"Query: \"{query}\"")
        for r in results:
            preview = r.get("content", "")[:80]
            print(f"  [{r.get('tool', r.get('type', '?'))}] {preview}")
        print()

    print(f"Summary: {mem.summary()}")


if __name__ == "__main__":
    main()
