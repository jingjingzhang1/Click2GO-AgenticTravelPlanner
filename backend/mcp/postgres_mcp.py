"""
Read-Only Database Engine (behind the MCP server)
=================================================
Provides schema discovery and safe read-only SQL execution against the
Click2GO database (SQLite or Postgres).

This class is the *engine*: it holds the query logic and the read-only
guardrails. It is exposed to agents/clients two ways:

  1. In-process (default) — instantiated directly for speed and offline use.
  2. Over MCP — wrapped by ``backend/mcp/db_server.py`` (a real FastMCP
     server) so the Route Optimizer agent, Claude Desktop, or any MCP client
     can call the same read-only tools over the protocol. See
     ``backend/mcp/client.py`` and ``get_db_explorer()`` in this package.

Agent 2 (Route Optimizer) uses this for intelligent exploration (e.g. finding
filler POIs to bridge transit gaps), while all writes go through strict
SQLAlchemy ORM functions in db_tools.py. The read-only guard here is the
security boundary that makes it safe to let an LLM compose exploratory queries.
"""
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from ..database import SessionLocal

logger = logging.getLogger(__name__)

# Disallowed SQL patterns — anything that mutates data
_WRITE_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)


class PostgresMCPServer:
    """
    Read-only database access layer for the Route Optimizer agent.

    Exposes three tools:
      - list_tables()         -> table names in the database
      - describe_table(name)  -> column names, types, and nullable flags
      - execute_query(sql)    -> run a read-only SELECT and return rows

    All mutations are blocked at the SQL level.
    """

    def list_tables(self) -> List[str]:
        """Return all table names in the database."""
        db = SessionLocal()
        try:
            inspector = inspect(db.bind)
            return inspector.get_table_names()
        finally:
            db.close()

    def describe_table(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Return column metadata for a table.

        Returns:
            List of dicts with keys: name, type, nullable
        """
        db = SessionLocal()
        try:
            inspector = inspect(db.bind)
            columns = inspector.get_columns(table_name)
            return [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                }
                for col in columns
            ]
        except Exception as e:
            logger.error("describe_table(%s) failed: %s", table_name, e)
            return []
        finally:
            db.close()

    def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Execute a read-only SQL query and return results.

        The query is validated to be a SELECT statement only.
        A LIMIT clause is enforced to prevent runaway queries.

        Returns:
            {"columns": [...], "rows": [[...], ...], "row_count": int}
        """
        if _WRITE_PATTERNS.search(sql):
            return {
                "error": "Write operations are not allowed via MCP. "
                         "Use the ORM tools for data mutations.",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

        stripped = sql.strip().rstrip(";")
        if not stripped.upper().startswith("SELECT"):
            return {
                "error": "Only SELECT queries are allowed.",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

        if "LIMIT" not in stripped.upper():
            stripped = f"{stripped} LIMIT {limit}"

        db = SessionLocal()
        try:
            result = db.execute(text(stripped), params or {})
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        except Exception as e:
            logger.error("execute_query failed: %s", e)
            return {
                "error": str(e),
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        finally:
            db.close()

    def find_nearby_pois(
        self,
        destination: str,
        lat: float,
        lng: float,
        radius_km: float = 2.0,
        exclude_names: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find cached POIs near a coordinate within a radius.
        Uses degree-based approximation for distance filtering.

        This is the key tool for the Route Optimizer to discover
        "filler" POIs when there are transit gaps in the schedule.
        """
        exclude_names = exclude_names or []
        degree_radius = radius_km / 111.0

        db = SessionLocal()
        try:
            # Build query compatible with SQLite
            query = text("""
                SELECT id, name, address, lat, lng, category, persona_score,
                       agent_note, persona_tags
                FROM poi_cache
                WHERE destination = :destination
                  AND lat IS NOT NULL AND lng IS NOT NULL
                  AND ABS(lat - :lat) < :deg_r
                  AND ABS(lng - :lng) < :deg_r
                ORDER BY ABS(lat - :lat) + ABS(lng - :lng)
                LIMIT :lim
            """)
            result = db.execute(query, {
                "destination": destination,
                "lat": lat,
                "lng": lng,
                "deg_r": degree_radius,
                "lim": limit,
            })
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]

            # Filter out excluded names in Python (SQLite doesn't support IN with params well)
            if exclude_names:
                rows = [r for r in rows if r.get("name") not in exclude_names]

            return rows[:limit]
        except Exception as e:
            logger.error("find_nearby_pois failed: %s", e)
            return []
        finally:
            db.close()
