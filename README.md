# Click2GO — Autonomous Multi-Agent Travel Planner

> **Plan perfectly. Arrive curious.**

Click2GO is a multi-agent AI travel planner that scrapes real social media posts from Xiaohongshu (Red Note), runs every location through Claude AI verification, clusters them into geographically optimized daily routes, and generates an interactive map with a styled PDF itinerary — all from a single request.

You tell it where you're going and what kind of traveller you are. It does the research so you don't have to — you show up with a great plan and a full tank of curiosity.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Multi-Agent Pipeline](#multi-agent-pipeline)
- [Tech Stack](#tech-stack)
- [Database Design](#database-design)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Key Engineering Decisions & Bugs Solved](#key-engineering-decisions--bugs-solved)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)
- [Offline / Fallback Mode](#offline--fallback-mode)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (index.html)                     │
│  Single-page web UI — no build step, vanilla JS                  │
│  • Planning form with persona picker                             │
│  • Real-time progress polling with agent step indicators         │
│  • Inline route map (iframe) with map style/toggle controls      │
│  • POI cards with verification badges + AI agent notes           │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (fetch)
┌────────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend (main.py)                     │
│  • POST /api/v1/plan → kicks off background pipeline             │
│  • GET  /plan/{id}/status → poll progress                        │
│  • GET  /plan/{id}/result → fetch itinerary + map/PDF URLs       │
│  • POST /plan/{id}/chat → Design Agent map controls              │
│  • Static file serving: /outputs/*.html, /outputs/*.pdf          │
└────────────────────────────┬────────────────────────────────────┘
                             │ BackgroundTasks
┌────────────────────────────▼────────────────────────────────────┐
│              LangGraph Multi-Agent Supervisor                     │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐         │
│  │   Agent 1     │   │   Agent 2     │   │   Agent 3     │       │
│  │  Knowledge    │──▶│    Route      │──▶│   Design &    │       │
│  │  Manager      │   │  Optimizer    │   │   UI Agent    │       │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘         │
│         │                   │                   │                 │
│  • Xiaohongshu      • K-Means          • Folium maps             │
│    scraping           clustering       • ReportLab PDF           │
│  • Claude AI         • Nearest-        • Map styling             │
│    verification        neighbour       • Distance labels         │
│  • Fuzzy              sorting          • Category-based          │
│    geocoding        • Transit gap        marker icons            │
│  • POI cache          filling (MCP)                              │
│    management                                                     │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SQLite Database (click2go.db)                   │
│  Tables: user_profiles, planning_sessions, pois, itinerary_days, │
│          poi_cache, chat_messages                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Pipeline

Click2GO uses the **LangGraph Supervisor** pattern to coordinate three specialized agents in a structured pipeline with conditional routing.

### Agent 1: Knowledge Manager (`knowledge_agent.py`)

The data-engineering agent. Keeps the destination database fresh and relevant.

**Pipeline:**
1. **Cache check** — Queries `poi_cache` table for the destination. If fresh data exists (< 72 hours) AND all requested persona categories are represented, returns immediately.
2. **Scrape** — Builds persona-specific Xiaohongshu search queries (e.g., `Tokyo美食推荐` for foodie, `Tokyo拍照打卡` for photography). Falls back to curated mock POI templates (8 per persona) when the MCP scraper is unavailable.
3. **Verify** — For each POI, fetches recent social media posts and sends them to Claude Sonnet for sentiment analysis. Claude evaluates three criteria:
   - **Status**: Is it currently open? Any closures or renovations?
   - **Seasonality**: Does the vibe match the travel dates?
   - **Persona match**: Does it suit the traveller's style?
   - Returns a structured JSON verdict: `INCLUDE` or `EXCLUDE` with a 0–10 persona score and a practical agent note.
4. **Filter** — Drops POIs flagged as `EXCLUDE` or `is_open: false`. Sorts remaining by persona score.
5. **Cache upsert** — Writes verified POIs to `poi_cache` for future sessions.
6. **Sufficiency check** — The Supervisor evaluates whether enough POIs were found. If not (and fewer than 2 attempts), it loops back for another scrape round with broader queries.

Each POI is tagged with its source `category` (foodie, photography, chilling, exercise) so filtering and map visualization work correctly.

### Agent 2: Route Optimizer (`route_agent.py`)

The logistical brain. Uses a hybrid MCP/ORM workflow.

**Pipeline:**
1. **K-Means clustering** — Groups geocoded POIs into `num_days` geographic zones using scikit-learn's KMeans. Each cluster becomes one day's itinerary.
2. **Nearest-neighbour sorting** — Within each cluster, sorts POIs with a greedy nearest-neighbour heuristic starting from the northernmost point (natural "morning start") to minimize backtracking.
3. **Transit gap filling** — Scans each day for gaps > 3km between consecutive stops. Uses the read-only Postgres MCP server to query `poi_cache` for nearby filler POIs to bridge gaps.
4. **ORM write** — Persists the finalized itinerary (day assignments, stop order) via strict SQLAlchemy ORM functions.

### Agent 3: Design & UI Agent (`design_agent.py`)

The frontend developer agent. Generates and iterates on visual outputs.

**Initial generation:**
- **PDF itinerary** — Branded A4 PDF via ReportLab with stats table, daily sections, AI notes, and persona scores.
- **Interactive Folium map** — POI markers color-coded by category (🍜 foodie = orange, 📷 photography = gold, ☕ chilling = blue, 🥾 exercise = green). Day-colored route polylines. Configurable tile layers.

**Post-generation controls (via chat endpoint):**
- Map style switching (Clean Light, Dark Mode, Satellite, Street Map)
- Route line show/hide
- Distance labels with estimated transit method (walk/bus/taxi/metro based on Haversine distance)
- Interpretation uses Claude Sonnet when available, falls back to keyword-based rule matching.

### Supervisor Flow

```
START → knowledge_manager → check_sufficiency ─┬─ ok ────→ route_optimizer → design_agent → END
                                                 ├─ retry ──→ knowledge_manager (loop)
                                                 └─ force ──→ route_optimizer (proceed with what we have)
```

The sufficiency check requires at least `max(days * 2, 4)` included POIs. If insufficient after 2 attempts, it forces the pipeline forward with whatever was collected.

---

## Tech Stack

### Backend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web framework | **FastAPI** | Async HTTP server, background tasks, auto-generated OpenAPI docs |
| Agent orchestration | **LangGraph** (StateGraph) | Multi-agent Supervisor pattern with conditional routing |
| AI verification | **Claude Sonnet** (Anthropic API) | POI sentiment analysis, design request interpretation |
| Route optimization | **scikit-learn** (KMeans) + **NumPy** | Geographic day clustering + greedy nearest-neighbour sorting |
| Map generation | **Folium** | Interactive Leaflet.js maps with custom DivIcon markers |
| PDF generation | **ReportLab** | Branded A4 itinerary PDFs |
| Database ORM | **SQLAlchemy 2.0** | SQLite persistence with seed database architecture |
| Settings | **pydantic-settings** | Type-safe configuration from `.env` files |
| Geocoding | **Google Maps API** (optional) | Address → coordinates; falls back to 60+ city lookup table with fuzzy matching |
| Social scraping | **Xiaohongshu MCP Server** (Docker) | Real travel post scraping; falls back to curated mock data |

### Frontend
| Component | Technology | Purpose |
|-----------|-----------|---------|
| UI | **Vanilla HTML/CSS/JS** | No build step, no framework — single `index.html` file |
| Map display | **iframe** embedding | Inline Folium map with controls below |
| Styling | **CSS custom properties** | Consistent theming with Click2GO brand colors |

### Infrastructure
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Database | **SQLite** | Zero-config, file-based. Seed database ships pre-populated via Git |
| Containerization | **Docker** | Xiaohongshu MCP scraper runs as a Docker container |
| Testing | **pytest** + **FastAPI TestClient** | 58 tests covering all agents, tools, endpoints, and MCP safety |

---

## Database Design

### Entity-Relationship Model

```
user_profiles ──< planning_sessions ──< pois
                                    ──< itinerary_days
                                    ──< chat_messages

poi_cache (standalone — destination-level cache)
```

### Tables

**`user_profiles`** — Stores trip parameters per planning request.
- `destination`, `start_date`, `end_date`, `personas` (comma-separated), `allergies` (JSON), `budget`

**`planning_sessions`** — Tracks each pipeline run.
- `id` (UUID), `status` (pending → scraping → verifying → routing → exporting → completed/failed)
- `total_pois_scraped`, `total_pois_verified`, `total_pois_included` — progress counters
- `error_message`, `created_at`, `completed_at`

**`pois`** — POIs assigned to a session's itinerary.
- Location: `name`, `address`, `lat`, `lng`, `category`
- Verification: `is_open`, `seasonal_match`, `persona_score`, `verification_recommendation`, `agent_note`
- Routing: `day_number`, `stop_order`

**`poi_cache`** — Destination-level cache managed by Agent 1.
- Same fields as `pois` plus `destination`, `persona_tags`, `verified_at`
- Cache freshness: 72-hour TTL based on `verified_at` timestamp

**`itinerary_days`** — Day-level routing metadata.
- `day_number`, `poi_sequence` (JSON), `cluster_center_lat/lng`

**`chat_messages`** — Design Agent chat history.
- `role` (user/assistant), `content`, `metadata` (JSON)

### Seed Database Architecture

The project uses a two-file SQLite strategy:
- `seed_database.sqlite` — Master file tracked in Git with pre-scraped POIs for popular cities
- `click2go.db` — User's local copy (gitignored), auto-created on first run by copying the seed

On startup, if the seed file is newer than the local copy, new POIs are merged into `poi_cache` without touching the user's itineraries or session data.

---

## API Reference

All endpoints are prefixed with `/api/v1`. Full Swagger UI available at `/docs`.

### Planning Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plan` | Start a planning session. Returns `session_id` immediately (HTTP 202). |
| `GET` | `/plan/{id}/status` | Poll pipeline progress (poll every 2–3s). |
| `GET` | `/plan/{id}/result` | Fetch finished itinerary, map URL, PDF URL, stats. |

### Chat / Design Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plan/{id}/chat` | Send a design command to Agent 3 (map style, route lines, etc.) |
| `GET` | `/plan/{id}/chat` | Retrieve chat history for a session. |

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the web UI (`frontend/index.html`). |
| `GET` | `/health` | Health check. |
| `GET` | `/docs` | Auto-generated Swagger UI. |

### Planning Request Body

```json
{
  "destination": "Tokyo",
  "start_date": "2026-04-01",
  "end_date": "2026-04-03",
  "personas": ["photography", "foodie"],
  "constraints": {
    "allergies": ["nuts"],
    "budget": "mid-range"
  },
  "max_pois_per_day": 5
}
```

- `personas`: any combination of `photography`, `chilling`, `foodie`, `exercise`
- `budget`: `budget`, `mid-range`, or `luxury`

### Session Status Flow

```
pending → scraping → verifying → routing → exporting → completed
                                                      → failed
```

---

## Frontend

The frontend is a single `index.html` file with no build step, no framework dependencies — vanilla HTML, CSS, and JavaScript.

### Planning Form
- Destination input with 60+ supported cities (fuzzy matching handles typos)
- Date picker with duration dropdown (1 day to 1 month)
- Persona grid: Photography (📷), Chilling (☕), Foodie (🍜), Exercise (🥾) — multi-select
- Budget selector, max stops per day, dietary restrictions

### Progress Display
- Real-time progress bar polling `/plan/{id}/status` every 2.5 seconds
- Four-step agent indicator showing which agent is currently active
- Agent labels (Agent 1, Agent 2, Agent 3) correspond to the three pipeline agents

### Results Display
- Stats row: POIs Discovered / AI-Verified / Included
- Day-by-day POI cards with:
  - Verification badge (Open / Closed / Unverified)
  - Persona star rating (0–10 scale)
  - AI agent note (practical travel tip)
- Inline route map embedded as iframe
- Map controls: tile style dropdown, route lines toggle, distance labels toggle
- Download links: full-screen map, PDF itinerary

---

## Key Engineering Decisions & Bugs Solved

### 1. POI Cache Inconsistency with Persona Switching

**Problem:** When a user generated a trip with "chilling" then regenerated with "chilling + foodie," the map only showed chilling spots. Conversely, switching to "foodie only" showed both types.

**Root cause:** Every POI was tagged with `persona_tags` set to ALL of the user's selected personas (e.g., `["chilling", "foodie"]`), not the POI's actual category. When the cache filter checked "does any of the user's new personas appear in this POI's tags?", chilling POIs matched on "chilling" even in a "foodie only" request — because they'd been tagged `["chilling", "foodie"]` from the previous run.

**Solution:**
1. Introduced a `category` field on each POI, set to the specific persona that sourced it (e.g., a dumpling shop gets `category: "foodie"`, a hiking trail gets `category: "exercise"`).
2. Changed `_filter_by_persona()` to filter by `category` instead of `persona_tags`.
3. Added a **persona coverage check** to the cache: even if enough total POIs exist, the cache is skipped unless ALL requested persona categories are represented. This forces a fresh scrape when the user adds a new travel style.

### 2. Blank Route Map (No POI Markers)

**Problem:** The generated map showed the correct region but no POI markers — just an empty tile layer.

**Root cause:** Mock POIs had no `lat`/`lng` fields. The geocoder was supposed to resolve addresses to coordinates, but mock addresses like "Tokyo" were too generic, and typos in destination names (e.g., "Vancuvour") caused the city lookup to fail silently.

**Solution:**
1. Mock POIs now embed `lat`/`lng` directly using city-center coordinates + random jitter (±0.03 degrees).
2. Added fuzzy geocoding with bidirectional substring matching and >60% character overlap fallback, so "Vancuvour" resolves to "Vancouver."

### 3. All POIs Showing as "Unverified"

**Problem:** Every POI in the itinerary displayed an "Unverified" badge despite passing through the verification pipeline.

**Root cause:** The verification agent's fallback path (used when no API key is available or when post parsing fails) returned `is_open: None` for some code paths. The frontend rendered `is_open === null` as "Unverified."

**Solution:** Changed ALL fallback paths in `VerificationAgent._fallback()` to return `is_open: True` with `persona_score: 7.0` and `seasonal_match: True`. In dev/demo mode, it's better to optimistically include POIs with a warning note ("Confirm status before visiting") than to show everything as unverified.

### 4. Static File Mount Race Condition

**Problem:** Generated map and PDF files returned 404 errors despite existing on disk.

**Root cause:** FastAPI's `StaticFiles` mount was registered before the `outputs/` directory was created. The `os.makedirs("outputs")` call was inside the lifespan handler, which runs AFTER `app.mount()`. FastAPI's `StaticFiles` validates the directory exists at mount time.

**Solution:** Moved `os.makedirs("outputs", exist_ok=True)` to module level, before `app.mount("/outputs", ...)`.

### 5. Design Agent Honesty Problem

**Problem:** When users sent requests the Design Agent couldn't handle (e.g., "add weather forecast overlay"), it responded with "I'll make those changes for you" — implying success when nothing changed.

**Solution:** Rewrote the rule-based fallback to honestly respond "I'm not sure how to make that change" and list available capabilities. The frontend was also redesigned from a free-text chat input to explicit dropdown/toggle controls, making it impossible to send unsupported requests.

### 6. Map Category Visualization

**Problem:** The "Highlight Style" dropdown applied a single persona color to ALL markers, which was misleading — a coffee shop and a hiking trail both turned orange if you selected "foodie highlight."

**Solution:** Removed the manual highlight dropdown entirely. Instead, each POI's map marker is automatically colored and labeled by its `category`:
- 🍜 Orange = Foodie
- 📷 Gold = Photography
- ☕ Blue = Chilling
- 🥾 Green = Exercise

The legend shows both the category color key and day-colored route lines.

---

## Quick Start

### Prerequisites

- Python 3.9+
- Docker (for the Xiaohongshu MCP scraper — optional)
- An [Anthropic API key](https://console.anthropic.com/) (optional — falls back to neutral verification)
- A [Google Maps API key](https://developers.google.com/maps) (optional — falls back to 60+ city lookup table)

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/click2GO.git
cd click2GO
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GOOGLE_MAPS_API_KEY=...   (optional)
```

### 3. Start the Xiaohongshu scraper (optional)

```bash
./start.sh      # start Docker container on localhost:18060
./login.sh      # scan QR code with the Xiaohongshu app to authenticate
```

Skip this step to use the offline mock data fallback.

### 4. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Open the app

Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

---

## Running Tests

```bash
python3 -m pytest tests/ -v
```

**58 tests** covering:
- API endpoints (root, health, planning CRUD, status polling)
- Planning session lifecycle (create → status → result)
- Route optimizer (K-Means clustering, nearest-neighbour sorting, even distribution)
- Verification agent (Claude response parsing, fallback behavior, schema validation)
- Social scraper (mock POIs, field completeness, post extraction, address parsing)
- Itinerary exporter (PDF generation, map generation, GeoJSON fallback)
- Postgres MCP safety (blocks INSERT, UPDATE, DELETE, DROP; allows SELECT)
- POI cache (upsert, update, retrieval)

Tests use an isolated SQLite database (tables recreated per test) and require no external services.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | No | Claude API key for POI verification + design interpretation. Falls back to neutral scores. |
| `GOOGLE_MAPS_API_KEY` | No | Geocoding precision. Falls back to 60+ city lookup table with fuzzy matching. |
| `REPLICATE_API_TOKEN` | No | Image generation (currently unused in UI). |
| `MCP_SERVER_URL` | No | Xiaohongshu scraper URL (default: `http://localhost:18060/mcp`). |
| `DATABASE_URL` | No | SQLAlchemy URL (default: `sqlite:///./click2go.db`). |
| `SECRET_KEY` | No | App secret (change for production). |
| `APP_ENV` | No | `development` or `production`. |

---

## Offline / Fallback Mode

All external dependencies degrade gracefully:

| Dependency | Fallback behavior |
|------------|------------------|
| **Xiaohongshu MCP scraper** | Returns curated mock POIs — 8 templates per persona with realistic names, descriptions, and scores |
| **Anthropic API (Claude)** | Verification returns `is_open: true`, `persona_score: 7.0` — all POIs included with "confirm status" note |
| **Google Maps API** | Falls back to 60+ city coordinate lookup table with fuzzy substring + character overlap matching |
| **ReportLab** | Exports plain text `.txt` instead of styled PDF |
| **Folium** | Exports `.geojson` instead of interactive HTML map |

The full pipeline runs end-to-end with **zero API keys configured**.

---

## Project Structure

```
click2GO/
├── frontend/
│   └── index.html                  Single-page web UI (no build step)
├── backend/
│   ├── main.py                     FastAPI app — serves UI, mounts routers
│   ├── config.py                   pydantic-settings — reads .env
│   ├── database.py                 SQLAlchemy engine + seed database strategy
│   ├── models.py                   ORM models (6 tables)
│   ├── schemas.py                  Pydantic request/response schemas
│   ├── agents/
│   │   ├── supervisor.py           LangGraph Multi-Agent Supervisor
│   │   ├── knowledge_agent.py      Agent 1: scrape → verify → cache
│   │   ├── verification_agent.py   Claude-powered POI verification
│   │   ├── route_agent.py          Agent 2: cluster → fill gaps → write
│   │   └── design_agent.py         Agent 3: maps, PDFs, map controls
│   ├── services/
│   │   └── route_optimizer.py      K-Means + nearest-neighbour algorithms
│   ├── tools/
│   │   ├── social_scraper_tool.py  Xiaohongshu API wrapper + mock data
│   │   ├── map_tool.py             Geocoding + Haversine distance
│   │   ├── itinerary_exporter.py   ReportLab PDF + Folium map generation
│   │   └── db_tools.py             Safe ORM write functions
│   ├── mcp/
│   │   └── postgres_mcp.py         Read-only SQL tool for Agent 2
│   └── routers/
│       ├── planning.py             POST /plan, GET /status, GET /result
│       └── chat.py                 POST/GET /plan/{id}/chat
├── tests/
│   └── test_click2go.py            58 tests
├── seed_database.sqlite            Pre-scraped POI cache (Git-tracked)
├── requirements.txt                Python dependencies
├── .env.example                    Environment variable template
└── README.md                       This file
```

---

## Acknowledgements

The Xiaohongshu data layer is built on top of the MCP server by [**@xpzouying**](https://github.com/xpzouying/xiaohongshu-mcp).

---

## Notes

- This project is for research and personal use. Comply with Xiaohongshu's terms of service.
- Do not make requests too frequently to avoid rate limiting or account suspension.
- Scraped data should not be redistributed or used commercially.
