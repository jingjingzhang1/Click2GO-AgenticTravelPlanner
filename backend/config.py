"""
Application configuration
=========================
Type-safe settings loaded from environment variables / ``.env`` via
``pydantic-settings``. Every field has a sane default so the full stack
boots with **zero configuration** — external providers degrade gracefully.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── AI / LLM ─────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # Optional OpenAI-compatible gateway (e.g. OpenRouter:
    # https://openrouter.ai/api/v1). When set, LLM calls route through it.
    openai_base_url: str = ""
    google_maps_api_key: str = ""

    # ── Database ─────────────────────────────────────────────────────────
    # SQLite is the zero-config default. Point this at a Postgres instance
    # to host your own planning database, e.g.
    #   postgresql+psycopg://click2go:click2go@localhost:5432/click2go
    database_url: str = "sqlite:///./click2go.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # ── External services ────────────────────────────────────────────────
    mcp_server_url: str = "http://localhost:18060/mcp"

    # ── Internal DB MCP server (Route Optimizer exploration) ─────────────
    # When enabled, the Route Optimizer reaches the read-only DB tools over a
    # real MCP round-trip (backend.mcp.db_server) instead of in-process.
    db_mcp_enabled: bool = False
    db_mcp_command: str = ""            # defaults to the current Python interpreter
    db_mcp_args: str = ""               # comma-separated; defaults to "-m,backend.mcp.db_server"

    # ── Observability ────────────────────────────────────────────────────
    log_level: str = "INFO"
    # "json" for machine-readable structured logs, "console" for humans.
    log_format: str = "console"
    service_name: str = "click2go"

    # ── App ──────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_version: str = "3.0.0"
    secret_key: str = "changethis"
    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Derived helpers ──────────────────────────────────────────────────
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgres")

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_mcp_args_list(self) -> List[str]:
        return [a.strip() for a in self.db_mcp_args.split(",") if a.strip()]


@lru_cache
def get_settings() -> "Settings":
    """Cached settings singleton (import-safe, test-overridable)."""
    return Settings()


settings = get_settings()
