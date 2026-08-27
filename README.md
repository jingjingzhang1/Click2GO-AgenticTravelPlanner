# Click2GO — Autonomous Multi-Agent Travel Companion

> **Just book a hotel. Click2GO plans the rest — and remembers the trip with you.**

[![CI](https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner/actions/workflows/ci.yml/badge.svg)](https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%20|%203.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-orange)
![Postgres](https://img.shields.io/badge/PostgreSQL-|%20SQLite-336791)
![License](https://img.shields.io/badge/license-MIT-green)

Click2GO is an all-in-one AI travel companion. You enter your destination and the
hotel you're staying at; three specialized agents coordinated by a **LangGraph
Supervisor** build a **hotel-anchored, day-of itinerary** — balanced by category,
routed to minimize travel, with reservation links and live transit directions for
every stop. Then, on the trip, it becomes your **travel journal**: tap any spot to
save photos, typed notes, and voice notes (transcribed in the browser), all
persisted to **your own database** and browsable across every trip you've planned.

One platform for **planning** *and* **remembering** — no more prep that drains the
curiosity out of a trip.

---

## Table of Contents

- [Highlights](#highlights)
- [What it does](#what-it-does)
- [System Architecture](#system-architecture)
- [Layered Backend Architecture](#layered-backend-architecture)
- [Multi-Agent Pipeline](#multi-agent-pipeline)
- [The Travel Journal](#the-travel-journal)
- [Database Design & Hosting Your Own](#database-design--hosting-your-own)
- [Observability](#observability)
- [Model Context Protocol (MCP)](#model-context-protocol-mcp)
- [Tech Stack](#tech-stack)
- [API Reference](#api-reference)
- [Quick Start](#quick-start)
- [Testing & CI](#testing--ci)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)

---

## Highlights

- **Hotel-anchored, day-of planning** — enter your hotel; every day's route starts
  there, with live Google Maps **transit directions** between stops and **booking
  links** for anything that needs a reservation. Reliable enough to just pull up on
  the day, no prep required.
- **Category-balanced routing** — geographic K-Means clustering with real business
  rules: coffee spots capped at 3/day, food at 5/day, so no day is all cafés.
- **Live travel journal** — tap any stop to attach photos, typed notes, and
  **voice notes transcribed in the browser** (Web Speech API), all saved to your DB.
  A **Travel Log** rolls it up; **My Trips** lets you browse, reopen, and delete any
  past trip's itinerary and memories.
- **Layered, testable backend** — strict `router → service → repository(DAO) →
  mapper → ORM` separation, plus a real **MCP server**, structured logging + a
  `/metrics` endpoint, Docker Compose, and CI.
- **Bring-your-own database** — zero-config SQLite by default; point `DATABASE_URL`
  at Postgres and it runs pooled connections with schema managed by **Alembic**.

---

## What it does

1. **Plan** — destination + hotel + travel styles (photography / chilling / foodie /
   exercise) + duration + max stops. Agents curate real places, score them, and route
   them into balanced days anchored to your hotel.
2. **Navigate day-of** — each stop shows a reservation/website button, a "book ahead"
   flag, and a one-tap **Directions** link (live Google Maps transit) from your hotel
   or the previous stop.
3. **Journal on the trip** — tap **＋ Memory** on any spot → note + voice-to-text +
   photo → saved to your DB. Spots with saved memories are visibly marked.
4. **Look back** — **📔 Travel Log** summarizes the trip; **📁 My Trips** browses every
   saved trip (with memory counts) so you can reopen or delete any of them.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (index.html)                     │
│  Single-page vanilla JS — planning form, itinerary, map,         │
│  journal modal (voice/photo), My Trips, Travel Log               │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (fetch) · X-Request-ID
┌────────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend (main.py)                     │
│  RequestContext middleware · structured logs · /metrics · /health │
│   Routers (thin controllers)                                      │
│        │ delegate to                                              │
│   Service layer  ── Planning · Journal · Image · Chat · Preference │
│        │ uses                                                     │
│   Repository (DAO) layer  ── Session/POI/Profile/Cache/Chat/Journal│
│        │ + Mappers (ORM ↔ DTO ↔ agent dicts)                      │
│   SQLAlchemy ORM                                                  │
└──────────┬───────────────────────────────────────────────────────┘
           │ BackgroundTasks
┌──────────▼───────────────────────┐
│  LangGraph Multi-Agent Supervisor │
│  Agent1 Knowledge → Agent2 Route  │
│         → Agent3 Design           │
└──────────┬────────────────────────┘
           │
┌──────────▼───────────────────────────────────────────────────────┐
│         Database  ·  SQLite (default)  or  PostgreSQL (opt-in)     │
│  user_profiles(+hotel) · planning_sessions · pois(+reservation) · │
│  itinerary_days · poi_cache · chat_messages ·                     │
│  journal_entries · journal_media       — managed by Alembic        │
└───────────────────────────────────────────────────────────────────┘
```

---

## Layered Backend Architecture

Every request flows one-directionally; each layer depends only on the one beneath it:

```
Router (backend/routers/*)       Thin controller. Parse input, call one service, return DTO.
   ▼
Service (backend/services/*)      Use-case logic + transaction boundaries + domain exceptions.
   ▼
Repository / DAO (backend/repositories/*)   All DB access; intention-revealing queries.
   ▼
Mapper (backend/mappers/*)        Pure ORM ↔ DTO ↔ agent-dict translation.
   ▼
SQLAlchemy ORM (backend/models.py)  →  SQLite / PostgreSQL
```

Domain exceptions (`NotFoundError → 404`, `ConflictError → 400`, `InProgressError →
202`) are translated to HTTP by global handlers in `main.py`, so the service layer
stays transport-agnostic and unit-testable.

---

## Multi-Agent Pipeline

A **LangGraph Supervisor** coordinates three agents with conditional retry routing.

**Agent 1 — Knowledge Manager (`knowledge_agent.py`):** pulls places from the
**Place provider** (curated datasets + optional Google Places — no more social-media
scraping), scores each with the LLM (via OpenRouter; degrades to curated scores with
no key), geocodes, and caches. Carries practical info: website, reservation link,
whether a booking is needed.

**Agent 2 — Route Optimizer (`route_agent.py`):** K-Means clusters places into
day-zones, then assigns each stop to the zone nearest your **hotel** under
**category caps** (coffee ≤ 3/day, food ≤ 5/day), and orders each day by
nearest-neighbour starting from the hotel.

**Agent 3 — Design Agent (`design_agent.py`):** branded PDF + interactive Folium map
(category-colored markers, day routes, transit/distance labels), plus deterministic
map toggles.

```
START → knowledge_manager → check_sufficiency ─┬─ ok ────→ route_optimizer → design_agent → END
                                                 ├─ retry ──→ knowledge_manager
                                                 └─ force ──→ route_optimizer
```

---

## The Travel Journal

The feature that makes Click2GO a companion, not just a planner:

- **Per-spot memories** — tap **＋ Memory** on any stop to attach a typed note, a
  voice note, and photos, tied to that exact place.
- **Voice → text** — the browser's Web Speech API transcribes speech live *and* the
  raw audio is captured and stored, so you get both a searchable transcript and the
  recording.
- **Your own database** — entries live in `journal_entries`, media in `journal_media`
  (files served from `/media`). Nothing is faked in-memory.
- **Visible markers** — spots that already have memories show a green
  "📔 View N memories" button so you can see at a glance what's been captured.
- **Travel Log** — `GET /plan/{id}/travel-log` rolls everything into a summary
  (counts + every entry, image, and playable recording).
- **My Trips** — `GET /trips` lists every saved trip with a memory count; reopen or
  **delete** any of them (cascade-deletes its data + files).

---

## Database Design & Hosting Your Own

**Tables:** `user_profiles` (incl. hotel), `planning_sessions`, `pois` (incl.
`website` / `reservation_url` / `needs_reservation` / `transit_note`),
`itinerary_days`, `poi_cache`, `chat_messages`, `journal_entries`, `journal_media`.

**Two ways to run:**

1. **SQLite (default, zero-config)** — a Git-tracked `seed_database.sqlite` ships
   curated cache data; a local `click2go.db` is created on first run.
2. **PostgreSQL (host your own)** — set `DATABASE_URL` to a Postgres DSN and the app
   switches to a pooled engine. Schema is provisioned with **Alembic**:
   ```bash
   export DATABASE_URL=postgresql+psycopg://click2go:click2go@localhost:5432/click2go
   alembic upgrade head
   ```
   `docker compose up` provisions Postgres, waits for it, migrates, and serves — so
   any fork gets its own hosted trip database with one command.

---

## Observability

Structured JSON logging (`LOG_FORMAT=json`) with a per-request correlation ID
(`X-Request-ID`) carried via `contextvars`; a `/metrics` Prometheus endpoint
(request counts + per-route latency); and an enriched `/health`.

---

## Model Context Protocol (MCP)

Click2GO ships a **real MCP server** (`backend/mcp/db_server.py`, FastMCP) exposing
the read-only database tools (`list_tables`, `describe_table`, `execute_query`,
`find_nearby_pois`) and consumes them through a **real MCP client** — the Route
Optimizer can reach the DB over a genuine MCP round-trip (`DB_MCP_ENABLED=true`), and
Claude Desktop / Cursor can add the server to query the travel DB. Writes never go
through MCP; the read-only guard is the security boundary.

```bash
python -m backend.mcp.db_server        # run over stdio
```

---

## Tech Stack

**Backend:** FastAPI · LangGraph (Supervisor) · MCP (server + client) · OpenAI-compatible
LLM via **OpenRouter** · scikit-learn KMeans + NumPy · Folium · ReportLab ·
SQLAlchemy 2.0 · Alembic · pydantic-settings.

**Data:** curated datasets + optional **Google Places**. **Journal voice:** Web
Speech API (browser). **DB:** PostgreSQL (psycopg 3) or SQLite. **Infra:** Docker
Compose · GitHub Actions CI · ruff/mypy. **Frontend:** vanilla HTML/CSS/JS, single file.

---

## API Reference

Prefixed with `/api/v1`; Swagger at `/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plan` | Start a planning session (202; body includes `hotel`). |
| `GET` | `/plan/{id}/status` | Poll pipeline progress. |
| `GET` | `/plan/{id}/result` | Itinerary + hotel + map/PDF URLs. |
| `DELETE` | `/plan/{id}` | Delete a trip and all its data + files. |
| `GET` | `/trips` | List every saved trip (with memory counts). |
| `POST` | `/plan/{id}/chat` · `GET` | Design-Agent chat (LLM) + history. |
| `POST` | `/plan/{id}/map-config` | Deterministic map toggles (no LLM). |
| `POST` | `/plan/{id}/journal` · `GET` | Add / list journal entries. |
| `POST` | `/journal/{entry_id}/media` | Attach a photo or audio file. |
| `GET` | `/plan/{id}/travel-log` | Trip summary rollup. |
| `POST/GET` | `/preferences` | Save / fetch a traveller profile. |
| `GET` | `/health` · `/metrics` | Ops endpoints. |

---

## Quick Start

```bash
git clone https://github.com/jingjingzhang1/Click2GO-AgenticTravelPlanner.git
cd Click2GO-AgenticTravelPlanner

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — add your OpenRouter/Google keys

uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open <http://127.0.0.1:8000>. It runs end-to-end with **zero keys** (curated places,
neutral scoring, offline geocoding). Add an OpenAI/OpenRouter key for real AI scoring;
add a Google Maps key for live Places/geocoding. Use **Chrome** for the in-browser
voice-to-text.

---

## Testing & CI

```bash
python3 -m pytest tests/ -q
```

**62 tests** cover the API endpoints, planning lifecycle, route optimizer, verification,
the Place provider, the travel journal, exporter, read-only SQL safety, POI cache, and
the MCP layer — all against an isolated SQLite DB, no external services.

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR: **tests** on Python
3.9 & 3.11, a **Postgres migration** smoke check, and an **advisory lint** (ruff).

---

## Environment Variables

Every variable is optional (see `.env.example`). Highlights:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | LLM via OpenAI or an OpenRouter gateway. |
| `GOOGLE_MAPS_API_KEY` | Google Places + precise geocoding (optional). |
| `DATABASE_URL` | SQLite default; Postgres DSN to host your own DB. |
| `DB_MCP_ENABLED` | Route Optimizer reaches the DB over MCP instead of in-process. |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` or `console`; verbosity. |

---

## Project Structure

```
Click2GO-AgenticTravelPlanner/
├── backend/
│   ├── main.py                 FastAPI app — middleware, exception handlers, ops
│   ├── config.py               typed settings (OpenRouter, providers, DB, MCP…)
│   ├── database.py             engine (SQLite/Postgres) + seed strategy
│   ├── models.py               SQLAlchemy ORM (8 tables)
│   ├── schemas.py              Pydantic DTOs
│   ├── routers/                thin controllers (planning, chat, image, journal, preferences)
│   ├── services/               use-case layer + domain exceptions + route optimizer
│   ├── repositories/           DAO layer (session, poi, profile, cache, chat, journal)
│   ├── mappers/                ORM ↔ DTO ↔ agent-dict translation
│   ├── observability/          structured logging · request middleware · metrics
│   ├── agents/                 LangGraph supervisor + 3 agents
│   ├── tools/
│   │   ├── place_provider.py         curated + Google Places (replaces scraping)
│   │   ├── map_tool.py               geocoding + Haversine + directions URLs
│   │   ├── itinerary_exporter.py     ReportLab PDF + Folium map
│   │   └── db_tools.py               agent-facing façade over repositories
│   └── mcp/                    read-only DB engine + real MCP server & client
├── frontend/index.html         single-page UI (planning, journal, My Trips, Travel Log)
├── migrations/                 Alembic env + versioned migrations
├── tests/                      pytest suite (62 tests)
├── Dockerfile · docker-compose.yml · .github/workflows/ci.yml
├── pyproject.toml · Makefile · requirements.txt · .env.example
└── DEMO_SCRIPT.md              demo recording script
```

---

## Notes

For research / personal use. Place data comes from curated datasets and, optionally,
the Google Places API (subject to Google's terms).
