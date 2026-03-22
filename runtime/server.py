"""
Event server — HTTP server that triggers agents from external events.

Turns agents into reactive infrastructure. Anything that can send
a POST request can trigger an agent: GitHub webhooks, form submissions,
monitoring alerts, payment processors, cron services, other agents.

Endpoints:
  POST /run          — run an agent with a task
  POST /webhook/:id  — fire a named webhook handler
  GET  /status       — server and job health
  GET  /sessions     — recent sessions

Usage:
  server = EventServer(port=8080)
  server.register_handler(
      "deploy-alert",
      agent_factory=lambda: DevOpsAgent(),
      task_template="A deployment alert was received: {payload}. Investigate and notify.",
  )
  server.start()

Calling it:
  curl -X POST http://localhost:8080/run \\
    -H "Content-Type: application/json" \\
    -d '{"task": "Check disk usage and summarize"}'

  curl -X POST http://localhost:8080/webhook/deploy-alert \\
    -d '{"service": "api", "event": "deploy_failed"}'
"""

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from runtime.logger import get_logger


@dataclass
class WebhookHandler:
    handler_id: str
    agent_factory: Callable
    task_template: str
    runtime_factory: Callable


class EventServer:
    """
    Lightweight HTTP server that dispatches agent runs.
    Zero dependencies beyond stdlib — no Flask, no FastAPI.

    Security: Bind to 0.0.0.0 only behind a firewall or with
    a secret token (set secret_token in config).
    """

    def __init__(
        self,
        port: int = 8080,
        host: str = "0.0.0.0",
        default_runtime_factory: Optional[Callable] = None,
        default_agent_factory: Optional[Callable] = None,
        secret_token: Optional[str] = None,
    ):
        self.port = port
        self.host = host
        self.default_runtime_factory = default_runtime_factory
        self.default_agent_factory = default_agent_factory
        self.secret_token = secret_token
        self.handlers: Dict[str, WebhookHandler] = {}
        self.recent_runs: List[Dict] = []
        self.logger = get_logger("event_server")
        self._server: Optional[HTTPServer] = None

    def register_handler(
        self,
        handler_id: str,
        agent_factory: Callable,
        task_template: str,
        runtime_factory: Optional[Callable] = None,
    ) -> "EventServer":
        """Register a named webhook handler. Returns self for chaining."""
        self.handlers[handler_id] = WebhookHandler(
            handler_id=handler_id,
            agent_factory=agent_factory,
            task_template=task_template,
            runtime_factory=runtime_factory or self.default_runtime_factory,
        )
        self.logger.info("handler_registered", handler_id=handler_id)
        return self

    def _run_agent_async(self, runtime_factory, agent_factory, task, run_record):
        """Execute an agent in a background thread."""
        try:
            loop = runtime_factory()
            agent = agent_factory()
            result = loop.run(agent, task=task)
            run_record.update({
                "status": "complete" if result.success else "failed",
                "steps": result.steps_taken,
                "session_id": result.session_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            self.logger.info(
                "run_complete",
                session=result.session_id,
                status=run_record["status"],
            )
        except Exception as e:
            run_record.update({"status": "error", "error": str(e)})
            self.logger.error("run_error", error=str(e))

    def _handle_request(self, method: str, path: str, headers: Dict, body: bytes) -> Dict:
        """Route a request and return a response dict."""
        # Token auth
        if self.secret_token:
            token = headers.get("X-Agent-Token") or headers.get("Authorization", "").replace("Bearer ", "")
            if token != self.secret_token:
                return {"status": 401, "body": {"error": "Unauthorized"}}

        parsed = urlparse(path)
        route = parsed.path.rstrip("/")

        # GET /status
        if method == "GET" and route == "/status":
            return {"status": 200, "body": {
                "ok": True,
                "handlers": list(self.handlers.keys()),
                "recent_run_count": len(self.recent_runs),
            }}

        # GET /sessions
        if method == "GET" and route == "/sessions":
            return {"status": 200, "body": {"runs": self.recent_runs[-20:]}}

        # POST /run — general task dispatch
        if method == "POST" and route == "/run":
            if not self.default_runtime_factory or not self.default_agent_factory:
                return {"status": 503, "body": {"error": "No default runtime/agent configured"}}

            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                return {"status": 400, "body": {"error": "Invalid JSON"}}

            task = payload.get("task", "").strip()
            if not task:
                return {"status": 400, "body": {"error": "Missing 'task' field"}}

            run_record = {
                "task": task[:100],
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
                "session_id": None,
            }
            self.recent_runs.append(run_record)
            if len(self.recent_runs) > 100:
                self.recent_runs = self.recent_runs[-100:]

            t = threading.Thread(
                target=self._run_agent_async,
                args=(self.default_runtime_factory, self.default_agent_factory, task, run_record),
                daemon=True,
            )
            t.start()

            return {"status": 202, "body": {"accepted": True, "task": task}}

        # POST /webhook/:handler_id
        if method == "POST" and route.startswith("/webhook/"):
            handler_id = route[len("/webhook/"):]
            if handler_id not in self.handlers:
                return {"status": 404, "body": {"error": f"No handler registered for '{handler_id}'"}}

            handler = self.handlers[handler_id]
            if not handler.runtime_factory:
                return {"status": 503, "body": {"error": f"No runtime configured for handler '{handler_id}'"}}

            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"raw": body.decode("utf-8", errors="replace")}

            task = handler.task_template.format(payload=json.dumps(payload))

            run_record = {
                "handler": handler_id,
                "task": task[:100],
                "triggered_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
                "session_id": None,
            }
            self.recent_runs.append(run_record)

            t = threading.Thread(
                target=self._run_agent_async,
                args=(handler.runtime_factory, handler.agent_factory, task, run_record),
                daemon=True,
            )
            t.start()

            return {"status": 202, "body": {"accepted": True, "handler": handler_id}}

        return {"status": 404, "body": {"error": f"No route: {method} {route}"}}

    def start(self, block: bool = True):
        """Start the HTTP server."""
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def _handle(self, method):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b""
                headers = dict(self.headers)

                response = server_ref._handle_request(method, self.path, headers, body)
                body_bytes = json.dumps(response["body"]).encode()

                self.send_response(response["status"])
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)

            def log_message(self, fmt, *args):
                server_ref.logger.debug("http", msg=fmt % args)

        self._server = HTTPServer((self.host, self.port), Handler)
        self.logger.banner(f"Event server listening on {self.host}:{self.port}")

        if block:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            t = threading.Thread(target=self._server.serve_forever, daemon=True)
            t.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self.logger.info("server_stopped")
