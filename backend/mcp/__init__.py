"""
MCP package
===========
Houses the read-only database engine (``postgres_mcp.PostgresMCPServer``), the
real MCP server that exposes it (``db_server``), and a synchronous client
(``client.DBMCPClient``).

``get_db_explorer()`` is the seam the Route Optimizer uses: by default it
returns the fast in-process engine; set ``DB_MCP_ENABLED=true`` to route the
same calls through a genuine MCP round-trip instead. Both objects expose an
identical ``find_nearby_pois(...)`` signature (duck-typed), so the agent code
doesn't change.
"""
from __future__ import annotations

import logging

from ..config import settings
from .postgres_mcp import PostgresMCPServer

logger = logging.getLogger(__name__)


def get_db_explorer():
    """
    Return the object the Route Optimizer uses for read-only DB exploration.

    * ``DB_MCP_ENABLED=false`` (default) → in-process ``PostgresMCPServer``.
    * ``DB_MCP_ENABLED=true``            → ``DBMCPClient`` (real MCP over stdio).

    Falls back to the in-process engine if the MCP client can't be constructed
    (e.g. the optional ``mcp`` package isn't installed), so the pipeline is
    never broken by the toggle.
    """
    if not settings.db_mcp_enabled:
        return PostgresMCPServer()

    try:
        from .client import DBMCPClient

        logger.info("Route Optimizer using DB access over MCP (stdio).")
        return DBMCPClient()
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP DB client unavailable (%s); using in-process engine.", exc)
        return PostgresMCPServer()


__all__ = ["PostgresMCPServer", "get_db_explorer"]
