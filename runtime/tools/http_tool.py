"""
HTTP tool — make requests to external APIs and services.

Agents can call any REST API, webhook, or web service.
This is how agents integrate with the outside world without
relying on centralized AI platforms.
"""

import json
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    raise ImportError("Install requests: pip install requests")

from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class HttpTool(BaseTool):
    def __init__(self, timeout: int = 15, default_headers: Optional[Dict] = None):
        super().__init__(
            name="http",
            description=(
                "Make HTTP requests (GET, POST, PUT, DELETE, PATCH) to external APIs or services. "
                "Use for fetching data, calling webhooks, interacting with REST APIs."
            )
        )
        self.timeout = timeout
        self.default_headers = default_headers or {}

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        method = input_data.get("method", "GET").upper()
        url = input_data.get("url", "").strip()
        headers = {**self.default_headers, **input_data.get("headers", {})}
        body = input_data.get("body")
        params = input_data.get("params")

        if not url:
            return ToolResult(success=False, output=None, error="No URL provided")

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
                params=params,
                timeout=self.timeout,
            )

            # Try JSON parse, fall back to text
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

            return ToolResult(
                success=response.ok,
                output={
                    "status_code": response.status_code,
                    "ok": response.ok,
                    "body": response_body,
                    "headers": dict(response.headers),
                },
                error=None if response.ok else f"HTTP {response.status_code}"
            )

        except requests.exceptions.Timeout:
            return ToolResult(
                success=False, output=None,
                error=f"Request timed out after {self.timeout}s"
            )
        except requests.exceptions.ConnectionError as e:
            return ToolResult(success=False, output=None, error=f"Connection error: {e}")
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to request"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "description": "HTTP method (default: GET)"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Optional HTTP headers as key-value pairs"
                    },
                    "body": {
                        "type": "object",
                        "description": "Optional JSON request body (for POST/PUT/PATCH)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional URL query parameters as key-value pairs"
                    }
                },
                "required": ["url"]
            }
        )
