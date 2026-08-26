# Click2GO — Autonomous Multi-Agent Travel Planner

> **Plan perfectly. Arrive curious.**

[![CI](https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner/actions/workflows/ci.yml/badge.svg)](https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%20|%203.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-orange)
![Postgres](https://img.shields.io/badge/PostgreSQL-|%20SQLite-336791)
![License](https://img.shields.io/badge/license-MIT-green)

Click2GO is a multi-agent AI travel planner. You tell it where you're going and
what kind of traveller you are; three specialized agents coordinated by a
**LangGraph Supervisor** scrape real social-media posts from Xiaohongshu (Red
Note), run every location through LLM verification, cluster them into
geographically optimized daily routes, and produce an **interactive map**, a
**branded PDF itinerary**, and a **Gemini-generated travel poster** — all from a
single request.

The codebase is built as a teaching-quality reference for **clean layered
architecture**: a strict `router → service → repository → ORM` separation with
dedicated mapper and provider layers, first-class **PostgreSQL** support with
**Alembic** migrations, **structured logging + Prometheus metrics**, a
one-command **Docker Compose** stack, and **CI** on every push.

---

## Table of Contents

- [Highlights](#highlights)
- [System Architecture](#system-architecture)
- [Layered Backend Architecture](#layered-backend-architecture)
- [Multi-Agent Pipeline](#multi-agent-pipeline)
- [Poster Generation (Gemini)](#poster-generation-gemini)
- [Database Design & Hosting Your Own](#database-design--hosting-your-own)
- [Observability](#observability)
- [Tech Stack](#tech-stack)
- [API Reference](#api-reference)
- [Quick Start](#quick-start)
- [Running with Docker + Postgres](#running-with-docker--postgres)
- [Testing & CI](#testing--ci)
- [Environment Variables](#environment-variables)
- [Key Engineering Decisions](#key-engineering-decisions)
- [Project Structure](#project-structure)

---

## Highlights

- **Layered, testable backend** — thin FastAPI controllers delegate to an
  application **service layer**, which orchestrates a **repository (DAO) layer**
  and pure **mappers**. No router touches the ORM directly; no service writes raw
  SQL.
- **Bring-your-own database** — zero-config SQLite by default; point
  `DATABASE_URL` at Postgres and the app runs pooled connections with schema
  managed by **Alembic migrations**. `docker compose up` gives every fork its own
  Postgres instance.
- **Multi-agent orchestration** — a LangGraph Supervisor coordinates a Knowledge
  Manager, a Route Optimizer, and a Design Agent with conditional retry routing.
- **Gemini 2.5 Flash Image posters** — a provider-strategy chain
  (Gemini → Replicate → Pollinations) renders a poster whose *text* (title, day
  labels, highlights) is legible — Gemini's headline strength.
- **Production hygiene** — structured JSON logging with request-ID correlation,
  a `/metrics` Prometheus endpoint, an enriched `/health`, typed settings, a
  Dockerfile that runs as non-root with a healthcheck, and GitHub Actions CI
  (ruff + pytest on SQLite and a Postgres migration smoke test).

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (index.html)                     │
│  Single-page web UI — no build step, vanilla JS                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (fetch) · X-Request-ID
┌────────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend (main.py)                     │
│  RequestContext middleware · structured logs · /metrics · /health │
│                                                                   │
│   Routers (thin controllers)                                      │
│        │  delegate to                                             │
│   Service layer  ── PlanningService · ImageService · ChatService  │
│        │  uses                     · PreferenceService            │
│   Repository (DAO) layer  ── Session/POI/Profile/Cache/Chat repos │
│        │  + Mappers (ORM ↔ DTO ↔ agent dicts)                     │
│   SQLAlchemy ORM                                                  │
└──────────┬───────────────────────────────────┬──────────────────┘
           │ BackgroundTasks                    │
┌──────────▼───────────────────────┐   ┌────────▼──────────────────┐
│   LangGraph Multi-Agent Supervisor│   │  Image provider chain      │
│   Agent1 Knowledge → Agent2 Route │   │  Gemini → Replicate →      │
│         → Agent3 Design           │   │  Pollinations              │
└──────────┬────────────────────────┘   └───────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────────────┐
│         Database  ·  SQLite (default)  or  PostgreSQL (opt-in)     │
│  user_profiles · planning_sessions · pois · itinerary_days ·      │
│  poi_cache · chat_messages     — schema managed by Alembic         │
└───────────────────────────────────────────────────────────────────┘
```

---

## Layered Backend Architecture

Every request flows through the same one-directional stack. Each layer has a
single responsibility and depends only on the layer beneath it:

```
HTTP request
   │
   ▼
Router (backend/routers/*)        Thin controller. Parses/validates input,
   │                              calls one service method, returns a DTO.
   ▼                              No business logic, no ORM.
Service (backend/services/*)      Application/use-case logic. Owns transaction
   │                              boundaries, raises domain exceptions
   ▼                              (NotFound/Conflict/InProgress). No raw SQL.
Repository / DAO (backend/repositories/*)   All database access lives here.
   │                              Intention-revealing query methods over one
   ▼                              aggregate each. Never commits on its own.
Mapper (backend/mappers/*)        Pure ORM ↔ DTO ↔ agent-dict translation.
   │
   ▼
SQLAlchemy ORM (backend/models.py)  →  SQLite / PostgreSQL
```

Domain exceptions are translated to HTTP status codes by global handlers in
`main.py` (`NotFoundError → 404`, `ConflictError → 400`, `InProgressError → 202`),
so the service layer stays completely transport-agnostic and unit-testable.

| Concern | Location |
|---------|----------|
| Controllers | `backend/routers/` |
| Use-case orchestration | `backend/services/` (`planning`, `image`, `chat`, `preference`) |
| Data access (DAO) | `backend/repositories/` (`session`, `poi`, `poi_cache`, `profile`, `chat`) |
| ORM ↔ DTO mapping | `backend/mappers/` |
| Domain errors | `backend/services/exceptions.py` |
| Cross-cutting (logging/metrics) | `backend/observability/` |
| Image provider strategy | `backend/tools/image_providers/` |

The agent-facing `backend/tools/db_tools.py` is kept as a stable façade over the
repository layer, so agent code and the existing test-suite have a simple import
surface while persistence details stay centralised.

---

## Multi-Agent Pipeline

Click2GO uses the **LangGraph Supervisor** pattern to coordinate three
specialized agents with conditional routing.

**Agent 1 — Knowledge Manager (`knowledge_agent.py`):** cache check (72h TTL +
persona coverage) → persona-specific Xiaohongshu scraping (mock fallback) → LLM
verification (open? seasonal? persona match?) → filter → cache upsert.

**Agent 2 — Route Optimizer (`route_agent.py`):** K-Means clustering into
`num_days` geographic zones → greedy nearest-neighbour sorting → transit-gap
filling via the read-only SQL tool → ORM write.

**Agent 3 — Design Agent (`design_agent.py`):** branded ReportLab PDF +
interactive Folium map (category-colored markers, day-colored routes,
distance/transit labels) + optional Gemini poster. Post-generation, deterministic
UI toggles bypass the LLM entirely while free-form chat uses it.

```
START → knowledge_manager → check_sufficiency ─┬─ ok ────→ route_optimizer → design_agent → END
                                                 ├─ retry ──→ knowledge_manager (loop)
                                                 └─ force ──→ route_optimizer (proceed)
```

---

## Poster Generation (Gemini)

The final flourish is a stylized travel poster. Rendering is abstracted behind a
**provider-strategy + chain-of-responsibility** design in
`backend/tools/image_providers/`:

| Provider | Model | Role | Output |
|----------|-------|------|--------|
| **Gemini** | `gemini-2.5-flash-image` ("Nano Banana") | primary | inline image bytes |
| **Replicate** | FLUX Schnell | fallback | remote URL |
| **Pollinations** | FLUX (keyless) | last resort | remote URL |

Providers are attempted in the order set by `IMAGE_PROVIDER_PRIORITY`; any whose
credentials are missing is skipped automatically. Gemini is primary because it
renders **legible text inside the image** — exactly what a travel-guide poster
needs (title, day labels, highlight captions). The `ImageService` normalises both
inline-bytes and remote-URL results into a locally-served asset under `/outputs`.

Trigger it explicitly via `POST /api/v1/plan/{id}/generate-image`, or set
`AUTO_GENERATE_POSTER=true` to render it as the final pipeline step.

```python
# gemini_provider.py (essence)
from google import genai
client = genai.Client(api_key=settings.gemini_api_key)
resp = client.models.generate_content(model="gemini-2.5-flash-image", contents=[prompt])
image_bytes = resp.candidates[0].content.parts[0].inline_data.data
```

---

## Database Design & Hosting Your Own

### Entity-Relationship Model

```
user_profiles ──< planning_sessions ──< pois
                                    ──< itinerary_days
                                    ──< chat_messages
poi_cache (standalone — destination-level cache)
```

Six tables: `user_profiles`, `planning_sessions`, `pois`, `itinerary_days`,
`poi_cache`, `chat_messages`. See `backend/models.py` for the full schema.

### Two ways to run

**1. SQLite (default, zero-config).** A Git-tracked `seed_database.sqlite` ships
pre-scraped POIs. On first run it's copied to a local `click2go.db`; after a
`git pull`, new seed POIs are merged into `poi_cache` without touching your
itineraries.

**2. PostgreSQL (host your own).** Set `DATABASE_URL` to a Postgres DSN and the
app switches to a pooled engine. Schema is provisioned with **Alembic**:

```bash
export DATABASE_URL=postgresql+psycopg://click2go:click2go@localhost:5432/click2go
alembic upgrade head          # create the schema
```

`docker compose up` provisions Postgres, waits for it, applies migrations, and
serves the API — so anyone who forks the repo gets their own hosted planning
database with a single command. Add or evolve tables with:

```bash
make revision m="add saved_trips table"   # alembic revision --autogenerate
make migrate                               # alembic upgrade head
```

---

## Observability

| Feature | Detail |
|---------|--------|
| **Structured logging** | `LOG_FORMAT=json` emits one JSON object per line (ts, level, logger, message, `request_id`, service). `console` format for local dev. |
| **Request correlation** | `RequestContextMiddleware` assigns/propagates an `X-Request-ID`, times every request, and logs a single access line. The ID rides a `contextvar` into every log record. |
| **Metrics** | `GET /metrics` exposes Prometheus-format counters (requests by method/status) and per-route average latency. |
| **Health** | `GET /health` returns status, version, environment, DB backend, and uptime. |

---

## Model Context Protocol (MCP)

Click2GO ships a **real MCP server** exposing the database's read-only tools, and
consumes them through a **real MCP client** — demonstrating both sides of the
protocol.

`backend/mcp/db_server.py` is a FastMCP (official `mcp` SDK) server that wraps the
read-only engine and exposes four tools: `list_tables`, `describe_table`,
`execute_query` (SELECT-only), and `find_nearby_pois`. Because the engine blocks
every mutating statement and forces a `LIMIT`, it is safe to let an LLM compose
exploratory queries against it — the read-only guard is the security boundary.

**Two consumers, one server:**

- **The Route Optimizer agent** normally calls the engine in-process for speed.
  Set `DB_MCP_ENABLED=true` and it instead reaches the same tools over a genuine
  MCP stdio round-trip (`backend/mcp/client.py`) — the app dogfooding its own MCP
  server. The `get_db_explorer()` factory swaps implementations behind an
  identical `find_nearby_pois(...)` signature, so agent code is unchanged.
- **Claude Desktop / Cursor / any MCP client** can add it as a local server and
  query the travel database directly:

  ```bash
  python -m backend.mcp.db_server        # run over stdio
  ```

  ```jsonc
  // claude_desktop_config.json  (see claude_desktop_config.example.json)
  {
    "mcpServers": {
      "click2go-db": {
        "command": "python",
        "args": ["-m", "backend.mcp.db_server"],
        "cwd": "/absolute/path/to/Click2GO-AgenticTravelPlanner"
      }
    }
  }
  ```

  Writes are never exposed over MCP — they always go through the ORM layer.

---

## Tech Stack

**Backend:** FastAPI · LangGraph (Supervisor) · **MCP** (server + client) · OpenAI `gpt-4o-mini`
(verification + design interpretation) · scikit-learn KMeans + NumPy · Folium ·
ReportLab · SQLAlchemy 2.0 · Alembic · pydantic-settings.

**Image:** Google Gen AI SDK (`gemini-2.5-flash-image`) · Replicate FLUX Schnell ·
Pollinations.

**Data:** PostgreSQL (psycopg 3) or SQLite. **Infra:** Docker + Docker Compose,
GitHub Actions CI, ruff + mypy + pre-commit. **Frontend:** vanilla HTML/CSS/JS,
single file, no build step.

---

## API Reference

All endpoints are prefixed with `/api/v1`; Swagger UI at `/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plan` | Start a planning session (HTTP 202, returns `session_id`). |
| `GET` | `/plan/{id}/status` | Poll pipeline progress. |
| `GET` | `/plan/{id}/result` | Fetch itinerary + map/PDF URLs. |
| `POST` | `/plan/{id}/generate-image` | Render the Gemini travel poster. Body: `{"language":"en"}`. |
| `POST` | `/plan/{id}/chat` | Free-form Design-Agent message (LLM). |
| `GET` | `/plan/{id}/chat` | Retrieve chat history. |
| `POST` | `/plan/{id}/map-config` | Deterministic map toggles (no LLM). |
| `POST` | `/preferences` | Save a traveller profile. |
| `GET` | `/preferences/{id}` | Retrieve a saved profile. |
| `GET` | `/health` · `/metrics` | Ops endpoints. |

### Planning request body

```json
{
  "destination": "Tokyo",
  "start_date": "2026-04-01",
  "end_date": "2026-04-03",
  "personas": ["photography", "foodie"],
  "constraints": { "allergies": ["nuts"], "budget": "mid-range" },
  "max_pois_per_day": 5,
  "language": "en"
}
```

---

## Quick Start

```bash
git clone https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner.git
cd Click2GO-AgenticTravelPlanner

pip install -r requirements.txt      # or: make install
cp .env.example .env                 # optional — fill in keys

uvicorn backend.main:app --reload --port 8000   # or: make run
```

Open <http://localhost:8000>. The full pipeline runs end-to-end with **zero API
keys** thanks to graceful fallbacks (mock scraper, neutral verification, keyless
poster provider, fuzzy geocoding).

To generate posters with legible text, add `GEMINI_API_KEY` to `.env`.

---

## Running with Docker + Postgres

```bash
docker compose up --build
```

This starts Postgres, waits for it to be healthy, applies Alembic migrations,
and serves the API on <http://localhost:8000> with structured JSON logs. Stop and
wipe volumes with `make docker-down`.

---

## Testing & CI

```bash
python3 -m pytest tests/ -v      # or: make test
```

**60 tests** cover the API endpoints, planning lifecycle, route optimizer,
verification agent, scraper, exporter, read-only SQL safety, POI cache, and the
MCP server/explorer factory. Tests run against an isolated SQLite database and
require no external services.

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR:

- **lint** — `ruff check` + `ruff format --check`
- **test** — pytest on Python 3.9 and 3.11 (SQLite)
- **test-postgres** — spins up a Postgres service, runs `alembic upgrade head`,
  and asserts all tables exist

Local quality gates: `make lint`, `make typecheck`, and `pre-commit install`
(config provided as `.pre-commit-config.yaml`).

---

## Environment Variables

Every variable is **optional**. Highlights (full list in `.env.example`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy URL. SQLite default; set a Postgres DSN to host your own DB. |
| `GEMINI_API_KEY` / `GEMINI_IMAGE_MODEL` | Primary poster provider + model. |
| `IMAGE_PROVIDER_PRIORITY` | Provider order, e.g. `gemini,replicate,pollinations`. |
| `AUTO_GENERATE_POSTER` | Render the poster as the final pipeline step. |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | POI verification + design interpretation. |
| `GOOGLE_MAPS_API_KEY` | Geocoding precision (falls back to 60+ city table). |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` or `console`; log verbosity. |
| `CORS_ORIGINS` | Comma-separated allowed origins. |

---

## Key Engineering Decisions

Beyond the layering and provider design above, the project documents a series of
real bugs solved during development:

1. **POI cache inconsistency with persona switching** — fixed by tagging each POI
   with its *sourcing* `category` and adding a persona-coverage check to the cache.
2. **Blank route map** — mock POIs now embed jittered city-center coordinates;
   fuzzy geocoding resolves typos like "Vancuvour" → "Vancouver".
3. **All POIs "Unverified"** — verification fallbacks now optimistically include
   POIs with a "confirm status" note instead of showing everything unverified.
4. **Static-file mount race** — `os.makedirs("outputs")` moved to module level
   before `app.mount(...)`.
5. **Design-Agent honesty** — the fallback now says "I'm not sure how to make that
   change" instead of implying success.
6. **Deterministic UI toggles routed through the LLM** — button clicks now hit a
   dedicated `/map-config` endpoint; the LLM is reserved for free-form chat.

---

## Project Structure

```
Click2GO-AgenticTravelPlanner/
├── backend/
│   ├── main.py                 FastAPI app — middleware, exception handlers, ops
│   ├── config.py               pydantic-settings (typed, cached)
│   ├── database.py             engine (SQLite/Postgres) + seed strategy
│   ├── models.py               SQLAlchemy ORM (6 tables)
│   ├── schemas.py              Pydantic DTOs
│   ├── routers/                thin controllers (planning, chat, image, preferences)
│   ├── services/               use-case layer + domain exceptions
│   ├── repositories/           DAO layer (one repo per aggregate)
│   ├── mappers/                ORM ↔ DTO ↔ agent-dict translation
│   ├── observability/          structured logging · request middleware · metrics
│   ├── agents/                 LangGraph supervisor + 3 agents
│   ├── services/route_optimizer.py   K-Means + nearest-neighbour
│   ├── tools/
│   │   ├── image_generator.py        prompt builder + provider orchestration
│   │   ├── image_providers/          gemini · replicate · pollinations
│   │   ├── social_scraper_tool.py    Xiaohongshu wrapper + mock data
│   │   ├── map_tool.py               geocoding + Haversine
│   │   ├── itinerary_exporter.py     ReportLab PDF + Folium map
│   │   └── db_tools.py               agent-facing façade over repositories
│   └── mcp/                    read-only DB engine + real MCP server & client
│       ├── postgres_mcp.py     read-only SQL engine (guardrails)
│       ├── db_server.py        FastMCP server exposing the DB tools
│       └── client.py           stdio MCP client (Route Optimizer dogfooding)
├── migrations/                 Alembic env + versioned migrations
├── tests/                      pytest suite (60 tests)
├── Dockerfile · docker-compose.yml · docker/entrypoint.sh
├── .github/workflows/ci.yml    lint · test · postgres migration check
├── pyproject.toml · Makefile · requirements.txt · .env.example
└── seed_database.sqlite        pre-scraped POI cache (Git-tracked)
```

---

## Acknowledgements

The Xiaohongshu data layer builds on the MCP server by
[**@xpzouying**](https://github.com/xpzouying/xiaohongshu-mcp).

## Notes

For research and personal use — comply with Xiaohongshu's terms of service, avoid
frequent requests, and don't redistribute scraped data.
