"""
MCP client for the Click2GO Database server
===========================================
A thin, **synchronous** wrapper around the official ``mcp`` stdio client so the
(synchronous) Route Optimizer agent can consume the database tools over a real
MCP round-trip — proving both sides of the protocol (server *and* client).

Each call spins up a short-lived stdio session against ``db_server.py``. Gap
filling is infrequent, so per-call sessions keep the code simple and robust; a
long-lived pooled session is an easy future optimisation.

This module is only imported when ``DB_MCP_ENABLED=true`` — the default path
uses the in-process engine, so the optional ``mcp`` dependency is never
required just to run the app or the tests.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

from ..config import settings

logger = logging.getLogger(__name__)


class DBMCPClient:
    """Synchronous facade over the Click2GO DB MCP server (stdio transport)."""

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
    ) -> None:
        self.command = command or settings.db_mcp_command or sys.executable
        self.args = args or settings.db_mcp_args_list or ["-m", "backend.mcp.db_server"]

    # ── public, sync API (mirrors PostgresMCPServer) ────────────────────
    def find_nearby_pois(
        self,
        destination: str,
        lat: float,
        lng: float,
        radius_km: float = 2.0,
        exclude_names: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        result = self.call_tool(
            "find_nearby_pois",
            {
                "destination": destination,
                "lat": lat,
                "lng": lng,
                "radius_km": radius_km,
                "exclude_names": exclude_names or [],
                "limit": limit,
            },
        )
        return result if isinstance(result, list) else []

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool by name and return its parsed result."""
        try:
            return asyncio.run(self._call_async(name, arguments))
        except Exception as exc:  # noqa: BLE001 — never crash the pipeline
            logger.warning("MCP call %s failed: %s", name, exc)
            return None

    # ── async plumbing ──────────────────────────────────────────────────
    async def _call_async(self, name: str, arguments: Dict[str, Any]) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=self.command, args=self.args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _parse_result(result)


def _parse_result(result: Any) -> Any:
    """Normalise a CallToolResult into plain Python (list/dict/scalar)."""
    # Prefer structured content when the SDK provides it.
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        # FastMCP wraps non-dict returns as {"result": <value>}.
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured

    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
    return None
