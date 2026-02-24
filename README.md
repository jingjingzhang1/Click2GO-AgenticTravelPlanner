# Click2GO — Agentic Travel Planner

> **Plan perfectly. Arrive curious.**

You know the feeling: you spend hours deep in travel blogs, spreadsheets, and review threads — and by the time you board the plane, you've already "been there" in your head. The wonder is gone before the trip even starts.

Click2GO does the research so you don't have to. Tell it where you're going and what kind of traveller you are. It scrapes thousands of real social media posts, runs every location past an AI that checks whether it's actually worth visiting right now, then hands you a tight day-by-day plan — without making you wade through any of it. You show up with a great itinerary *and* a full tank of curiosity.

---

## How It Works

Click2GO runs a multi-stage LangGraph pipeline entirely in the background:

1. **Scrape** — Searches Xiaohongshu (Red Note) for real traveller posts about your destination
2. **Verify** — A Claude AI agent reads recent posts for each location to check if it's open, seasonal, and a fit for your travel style
3. **Filter** — Drops any location flagged as closed, irrelevant, or low-scoring
4. **Optimize** — K-Means clustering groups locations into daily zones; nearest-neighbour sorting minimizes walking
5. **Export** — Produces a styled PDF itinerary and an interactive HTML map

The frontend polls for progress and renders the full itinerary with per-stop AI notes, persona scores, and download links.

---

## Features

- **4 travel personas**: Photography, Chilling, Foodie, Exercise — mix and match
- **Claude-powered POI verification**: Each location is vetted against live Xiaohongshu sentiment before it appears in your plan
- **Smart daily routing**: K-Means + greedy nearest-neighbour keeps each day geographically tight
- **Graceful offline mode**: Falls back to curated mock data if the scraper or APIs are unavailable
- **PDF + interactive map**: ReportLab-generated PDF and Folium HTML map, colour-coded by day
- **Dietary & budget constraints**: Passed directly into the AI verification prompt
- **SQLite persistence**: Every session, POI, and verification result is stored for replay or debugging

---

## Architecture

```
frontend/index.html         Single-page web UI (no build step)
backend/
  main.py                   FastAPI app — serves UI, mounts routers, runs background tasks
  routers/
    planning.py             POST /plan, GET /plan/{id}/status, GET /plan/{id}/result
    preferences.py          POST/GET /preferences
  agents/
    orchestrator.py         LangGraph state machine (scrape → verify → filter → optimize → export)
    verification_agent.py   Claude Opus 4.6 — decides INCLUDE / EXCLUDE per POI
  services/
    route_optimizer.py      K-Means clustering + nearest-neighbour day routing
  tools/
    social_scraper_tool.py  Wraps XiaohongshuAPI; offline mock fallback
    map_tool.py             Google Maps geocoding + Haversine distance
    itinerary_exporter.py   ReportLab PDF + Folium interactive map
  models.py                 SQLAlchemy ORM (UserProfile, PlanningSession, POI, ItineraryDay)
  schemas.py                Pydantic request / response models
  config.py                 pydantic-settings — reads .env
  database.py               SQLAlchemy engine + session factory
tests/
  test_click2go.py          35+ unit and integration tests
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for the Xiaohongshu MCP scraper)
- An [Anthropic API key](https://console.anthropic.com/) (Claude)
- A [Google Maps API key](https://developers.google.com/maps) (optional, falls back to a city lookup table)

### 1. Clone and install dependencies

```bash
git clone https://github.com/your-username/click2GO.git
cd click2GO
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in at minimum:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GOOGLE_MAPS_API_KEY=...   (optional)
```

### 3. Start the Xiaohongshu scraper (optional)

The MCP scraper runs as a Docker container. Skip this step if you want to use offline mock data.

```bash
./start.sh      # start Docker container on localhost:18060
./login.sh      # scan QR code with the Xiaohongshu app to authenticate
```

### 4. Start the backend

```bash
./run_backend.sh
# or manually:
uvicorn backend.main:app --reload --port 8000
```

### 5. Open the app

Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

---

## API Reference

All endpoints are prefixed with `/api/v1`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/plan` | Start a planning session. Returns `session_id` immediately (HTTP 202). |
| `GET` | `/plan/{id}/status` | Poll pipeline progress. Poll every 2–3 seconds. |
| `GET` | `/plan/{id}/result` | Fetch the finished itinerary, PDF URL, and map URL. |
| `POST` | `/preferences` | Save user preferences. |
| `GET` | `/preferences/{id}` | Retrieve saved preferences. |
| `GET` | `/health` | Health check. |
| `GET` | `/docs` | Auto-generated Swagger UI. |

### Planning request body

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
  "max_pois_per_day": 5,
  "language": "en"
}
```

`personas` accepts any combination of: `photography`, `chilling`, `foodie`, `exercise`.
`budget` accepts: `budget`, `mid-range`, `luxury`.

### Session status values

`pending` → `scraping` → `verifying` → `routing` → `exporting` → `completed` (or `failed`)

---

## Running Tests

```bash
python3 -m pytest tests/ -v
```

The test suite covers route optimization, geocoding, verification agent schema, PDF/map export, scraper mocking, and all HTTP endpoints.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for POI verification |
| `GOOGLE_MAPS_API_KEY` | No | Geocoding precision; falls back to city lookup |
| `MCP_SERVER_URL` | No | Xiaohongshu scraper URL (default: `http://localhost:18060/mcp`) |
| `DATABASE_URL` | No | SQLAlchemy URL (default: `sqlite:///./click2go.db`) |
| `SECRET_KEY` | No | App secret (change for production) |
| `APP_ENV` | No | `development` or `production` |

---

## Offline / Fallback Mode

All external dependencies degrade gracefully:

- **Xiaohongshu scraper unavailable** → Returns persona-specific mock POIs (8 templates per persona)
- **Google Maps unavailable** → Falls back to a hardcoded table of 50+ city coordinates with small jitter
- **Anthropic API unavailable** → Verification returns neutral scores; all POIs are included
- **ReportLab unavailable** → Exports plain text `.txt` instead of PDF
- **Folium unavailable** → Exports `.geojson` instead of HTML map

This means the full pipeline runs end-to-end even with no API keys configured.

---

## Acknowledgements

The Xiaohongshu data layer is built on top of the MCP server by **[@xpzouying](https://github.com/xpzouying/xiaohongshu-mcp)**. Many thanks for making that infrastructure available.

---

## Notes

- This project is for research and personal use. Comply with Xiaohongshu's terms of service.
- Do not make requests too frequently to avoid rate limiting or account suspension.
- Scraped data should not be redistributed or used commercially.
