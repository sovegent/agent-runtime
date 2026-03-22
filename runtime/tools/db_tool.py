"""
Database tool — query and write to databases directly.

No API layer, no ORM. Agents can read and write data
exactly as your application does.

Supports: SQLite (zero-config), PostgreSQL (requires psycopg2)

Safety model:
  - READ mode (default): SELECT, EXPLAIN, SHOW, PRAGMA only
  - WRITE mode: must pass allow_writes=True in config
  - Parameterized queries prevent injection
  - Row limit prevents runaway SELECTs
"""

import sqlite3
import json
from typing import Any, Dict, List, Optional
from runtime.tools.base_tool import BaseTool, ToolResult
from runtime.llm.base import ToolDefinition


class DatabaseTool(BaseTool):
    def __init__(
        self,
        connection_string: Optional[str] = None,
        db_type: str = "sqlite",
        allow_writes: bool = False,
        row_limit: int = 500,
    ):
        """
        Args:
            connection_string: For SQLite: path to .db file.
                               For Postgres: "postgresql://user:pass@host:5432/dbname"
            db_type: "sqlite" or "postgres"
            allow_writes: If False, only SELECT/EXPLAIN/SHOW/PRAGMA are permitted
            row_limit: Maximum rows returned per query
        """
        super().__init__(
            name="database",
            description=(
                "Execute SQL queries against a database. "
                "Use for reading records, running analytics, updating data, "
                "or inspecting schema. Supports SQLite and PostgreSQL."
            )
        )
        self.connection_string = connection_string
        self.db_type = db_type.lower()
        self.allow_writes = allow_writes
        self.row_limit = row_limit

        self._READONLY_PREFIXES = ("select", "explain", "show", "pragma", "describe", "with")

    def _is_readonly(self, query: str) -> bool:
        first = query.strip().lower().lstrip("(").split()[0]
        return first in self._READONLY_PREFIXES

    def _connect(self):
        if self.db_type == "sqlite":
            conn = sqlite3.connect(self.connection_string or ":memory:")
            conn.row_factory = sqlite3.Row
            return conn
        elif self.db_type == "postgres":
            try:
                import psycopg2
                import psycopg2.extras
            except ImportError:
                raise ImportError("Install psycopg2: pip install psycopg2-binary")
            return psycopg2.connect(self.connection_string)
        else:
            raise ValueError(f"Unsupported db_type: {self.db_type}. Use 'sqlite' or 'postgres'.")

    def _rows_to_dicts(self, cursor, rows) -> List[Dict]:
        if not rows:
            return []
        if self.db_type == "sqlite":
            return [dict(row) for row in rows]
        else:
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in rows]

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        query = input_data.get("query", "").strip()
        params = input_data.get("params", [])
        connection_string = input_data.get("connection_string") or self.connection_string

        if not query:
            return ToolResult(success=False, output=None, error="No query provided")
        if not connection_string and self.db_type != "sqlite":
            return ToolResult(success=False, output=None, error="No connection_string provided")

        # Write guard
        if not self.allow_writes and not self._is_readonly(query):
            return ToolResult(
                success=False, output=None,
                error=(
                    f"Write operations are disabled (allow_writes=False). "
                    f"Query starts with a write keyword. "
                    f"Set allow_writes=True in DatabaseTool config to enable writes."
                )
            )

        conn = None
        try:
            # Temporarily override connection string if provided in input
            original = self.connection_string
            if connection_string:
                self.connection_string = connection_string

            conn = self._connect()
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            is_select = self._is_readonly(query)

            if is_select:
                rows = cursor.fetchmany(self.row_limit)
                data = self._rows_to_dicts(cursor, rows)
                total = len(data)
                truncated = total == self.row_limit

                return ToolResult(success=True, output={
                    "rows": data,
                    "row_count": total,
                    "truncated": truncated,
                    "truncated_at": self.row_limit if truncated else None,
                    "columns": list(data[0].keys()) if data else [],
                })
            else:
                conn.commit()
                affected = cursor.rowcount
                return ToolResult(success=True, output={
                    "rows_affected": affected,
                    "message": f"Query executed. {affected} row(s) affected.",
                })

        except Exception as e:
            if conn and not self._is_readonly(query):
                try:
                    conn.rollback()
                except Exception:
                    pass
            return ToolResult(success=False, output=None, error=str(e))
        finally:
            if conn:
                conn.close()
            if connection_string:
                self.connection_string = original

    def get_definition(self) -> ToolDefinition:
        write_note = "" if self.allow_writes else " Write operations (INSERT/UPDATE/DELETE) are currently disabled."
        return ToolDefinition(
            name=self.name,
            description=self.description + write_note,
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute. Use parameterized queries with ? (SQLite) or %s (Postgres) for values."
                    },
                    "params": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of parameter values for parameterized queries (e.g., ['value1', 'value2'])"
                    },
                    "connection_string": {
                        "type": "string",
                        "description": "Optional connection string to override the default. SQLite: file path. Postgres: postgresql://user:pass@host/db"
                    }
                },
                "required": ["query"]
            }
        )
