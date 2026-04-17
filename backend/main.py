import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import create_tables
from .routers import chat, image, planning, preferences


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    create_tables()
    yield
    # ── Shutdown ─────────────────────────────────────────────


app = FastAPI(
    title="Click2GO API",
    description=(
        "Autonomous Multi-Agent Travel Planner — "
        "Three specialized agents (Knowledge Manager, Route Optimizer, "
        "Design Agent) coordinate via a LangGraph Supervisor to synthesise "
        "Xiaohongshu social intelligence with Claude AI verification, "
        "K-Means route optimisation, and interactive map generation."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure outputs dir exists BEFORE mounting (avoids race with lifespan)
os.makedirs("outputs", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Serve the frontend HTML
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.include_router(planning.router, prefix="/api/v1", tags=["Planning"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(image.router, prefix="/api/v1", tags=["Image"])
app.include_router(preferences.router, prefix="/api/v1", tags=["Preferences"])


@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """Serve the Click2GO web UI."""
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, media_type="text/html")
    return {"name": "Click2GO", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", tags=["Root"])
async def health_check():
    return {"status": "healthy", "service": "click2go", "version": "2.0.0"}
