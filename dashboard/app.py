"""
Web dashboard — real-time agent observability.

Watch agents run live. Inspect session memory. Replay past runs.
This is how you go from "hoping the agent did the right thing"
to actually seeing it.

Run it:
  python -m dashboard.app

Then open http://localhost:5001
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Allow import from parent
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from flask import Flask, jsonify, render_template, request
except ImportError:
    raise ImportError("Install flask: pip install flask")

from runtime.config import load_config
from runtime.memory.memory_store import MemoryStore
from runtime.memory.session import SessionManager

app = Flask(__name__, template_folder="templates")
config = load_config()
sessions = SessionManager(storage_path="./data/sessions")


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/sessions")
def api_sessions():
    n = int(request.args.get("n", 30))
    rows = sessions.list_sessions(n=n)
    return jsonify({"sessions": rows})


@app.route("/api/sessions/<session_id>")
def api_session(session_id):
    session = sessions.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    memory = MemoryStore(
        session_id=session_id,
        storage_path=config.memory.storage_path,
        persist=True,
    )
    entries = memory.get_all()
    return jsonify({
        "session": session,
        "entries": entries,
        "summary": memory.summary(),
    })


@app.route("/api/sessions/<session_id>/steps")
def api_session_steps(session_id):
    memory = MemoryStore(
        session_id=session_id,
        storage_path=config.memory.storage_path,
        persist=True,
    )
    return jsonify({"steps": memory.get_steps()})


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "sessions": len(sessions.list_sessions(100))})


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 5001))
    print(f"\n  Dashboard → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
