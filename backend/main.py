"""
Click2GO API — application entrypoint
=====================================
Wires together configuration, observability (structured logging + request
middleware + metrics), the layered routers, and the domain→HTTP exception
handlers. Business logic lives in the service layer; this module is pure
composition.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import create_tables
from .observability import (
    METRICS,
    RequestContextMiddleware,
    configure_logging,
    get_logger,
    render_prometheus,
)
from .routers import chat, image, journal, planning, preferences
from .services.exceptions import ConflictError, InProgressError, NotFoundError

configure_logging()
logger = get_logger("click2go.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("starting Click2GO", extra={"env": settings.app_env,
                                             "db": settings.database_url.split("://")[0]})
    create_tables()
    yield
    # ── Shutdown ─────────────────────────────────────────────
    logger.info("shutting down Click2GO")


app = FastAPI(
    title="Click2GO API",
    description=(
        "Autonomous Multi-Agent Travel Planner — three specialized agents "
        "(Knowledge Manager, Route Optimizer, Design Agent) coordinate via a "
        "LangGraph Supervisor to synthesise Xiaohongshu social intelligence with "
        "LLM verification, K-Means route optimisation, Gemini poster generation, "
        "and interactive map generation. Built with a layered "
        "router → service → repository architecture."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

# ── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Domain → HTTP exception handlers ─────────────────────────────────────────
@app.exception_handler(NotFoundError)
async def _not_found(_: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc) or "Not found"})


@app.exception_handler(ConflictError)
async def _conflict(_: Request, exc: ConflictError):
    return JSONResponse(status_code=400, content={"detail": str(exc) or "Bad request"})


@app.exception_handler(InProgressError)
async def _in_progress(_: Request, exc: InProgressError):
    return JSONResponse(
        status_code=202,
        content={"detail": f"Session still in progress: {exc}"},
    )


# Ensure asset dirs exist BEFORE mounting (avoids race with lifespan).
os.makedirs("outputs", exist_ok=True)
os.makedirs("media", exist_ok=True)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/media", StaticFiles(directory="media"), name="media")

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(planning.router, prefix="/api/v1", tags=["Planning"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(image.router, prefix="/api/v1", tags=["Image"])
app.include_router(preferences.router, prefix="/api/v1", tags=["Preferences"])
app.include_router(journal.router, prefix="/api/v1", tags=["Journal"])


# ── Root / ops endpoints ─────────────────────────────────────────────────────
@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """Serve the Click2GO web UI."""
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index, media_type="text/html")
    return {"name": "Click2GO", "version": settings.app_version, "docs": "/docs"}


@app.get("/health", tags=["Ops"])
async def health_check():
    """Liveness + basic runtime facts."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": settings.database_url.split("://")[0],
        "uptime_seconds": METRICS.snapshot()["uptime_seconds"],
    }


@app.get("/metrics", tags=["Ops"], response_class=PlainTextResponse)
async def metrics():
    """Prometheus-format metrics for scraping."""
    return render_prometheus()
