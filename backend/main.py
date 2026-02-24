import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import create_tables
from .routers import planning, preferences


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    create_tables()
    os.makedirs("outputs", exist_ok=True)
    yield
    # ── Shutdown (nothing to clean up for now) ────────────────


app = FastAPI(
    title="Click2GO API",
    description=(
        "Agentic Travel Planning Engine – "
        "synthesises Xiaohongshu social intelligence with "
        "Claude AI verification and K-Means route optimisation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated PDFs and maps as static files
if os.path.isdir("outputs"):
    app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Serve the frontend HTML
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

app.include_router(planning.router, prefix="/api/v1", tags=["Planning"])
app.include_router(preferences.router, prefix="/api/v1", tags=["Preferences"])


@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """Serve the Click2GO web UI."""
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, media_type="text/html")
    return {"name": "Click2GO", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["Root"])
async def health_check():
    return {"status": "healthy", "service": "click2go"}
