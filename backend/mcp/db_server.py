"""
Click2GO Database MCP Server
============================
A **real** Model Context Protocol server (built on the official ``mcp`` SDK's
FastMCP) that exposes the read-only database engine as MCP tools. Any MCP
client can connect and safely explore the travel database:

  * the Route Optimizer agent (see ``client.py`` + ``get_db_explorer``),
  * Claude Desktop / Cursor (add it as a local stdio server),
  * any other MCP-aware tool.

Every tool is read-only: the underlying engine blocks INSERT/UPDATE/DELETE/DROP
and enforces a LIMIT, so exposing this to an LLM cannot mutate or overload the
database. Writes always go through the ORM layer, never through MCP.

Run standalone (stdio transport)::

    python -m backend.mcp.db_server

Register with Claude Desktop (claude_desktop_config.json)::

    {
      "mcpServers": {
        "click2go-db": {
          "command": "python",
          "args": ["-m", "backend.mcp.db_server"]
        }
      }
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .postgres_mcp import PostgresMCPServer

# The FastMCP import is deferred to build time so that importing this module's
# symbols (or the package) does not hard-require the optional ``mcp`` dependency.
try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - only hit when mcp isn't installed
    FastMCP = None  # type: ignore[assignment]

SERVER_NAME = "click2go-db"

# Shared read-only engine instance (holds the guardrails + query logic).
_engine = PostgresMCPServer()


def build_server() -> "FastMCP":
    """Construct the FastMCP server and register the read-only DB tools."""
    if FastMCP is None:
        raise RuntimeError(
            "The 'mcp' package is required to run the MCP server. "
            "Install it with: pip install mcp"
        )

    mcp = FastMCP(
        SERVER_NAME,
        instructions=(
            "Read-only access to the Click2GO travel database. Use list_tables "
            "and describe_table to learn the schema, then execute_query (SELECT "
            "only) or find_nearby_pois for geospatial lookups. Writes are not "
            "permitted through this server."
        ),
    )

    @mcp.tool()
    def list_tables() -> List[str]:
        """List all table names in the Click2GO database."""
        return _engine.list_tables()

    @mcp.tool()
    def describe_table(table_name: str) -> List[Dict[str, Any]]:
        """Return column metadata (name, type, nullable) for a table."""
        return _engine.describe_table(table_name)

    @mcp.tool()
    def execute_query(sql: str, limit: int = 100) -> Dict[str, Any]:
        """
        Run a read-only SELECT query and return {columns, rows, row_count}.
        Non-SELECT / mutating statements are rejected.
        """
        return _engine.execute_query(sql, limit=limit)

    @mcp.tool()
    def find_nearby_pois(
        destination: str,
        lat: float,
        lng: float,
        radius_km: float = 2.0,
        exclude_names: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find cached POIs near a coordinate within a radius (km). Used by the
        Route Optimizer to discover filler POIs that bridge transit gaps.
        """
        return _engine.find_nearby_pois(
            destination=destination,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            exclude_names=exclude_names,
            limit=limit,
        )

    return mcp


def main() -> None:
    """Entry point: run the server over stdio."""
    build_server().run()  # stdio transport by default


if __name__ == "__main__":
    main()
