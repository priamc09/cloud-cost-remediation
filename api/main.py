"""
FastAPI application entry point.

Lifespan
────────
startup  → configure logging → resolve DB provider → download SQLite blob → init tables
shutdown → upload SQLite blob (sqlite only)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.logging_config import configure_logging
from api.database import init_db
from api.dependencies import get_db_storage_dep
from api.routers import jobs, dashboard, findings, scripts, resources, costs

# Configure logging before any other module logs
from api.config import get_settings as _gs
configure_logging(_gs().LOG_LEVEL)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    cfg = _gs()
    provider_name = cfg.DATABASE_PROVIDER.lower()
    logger.info("=== Cloud Cost Optimizer starting up ===")
    logger.info("Database provider: %s", provider_name)

    if provider_name == "sqlite":
        try:
            storage = get_db_storage_dep()
            logger.info("Downloading optimizer.db from blob storage…")
            storage.download_db()
        except Exception:
            logger.warning(
                "Blob DB download failed — will start with a fresh local database.",
                exc_info=True,
            )

    try:
        logger.info("Initialising database tables…")
        init_db()
        logger.info("Database tables ready.")
    except Exception:
        logger.critical("Failed to initialise database — cannot start.", exc_info=True)
        raise

    logger.info("=== Startup complete. API ready. ===")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("=== Shutting down ===")
    if provider_name == "sqlite":
        try:
            storage = get_db_storage_dep()
            logger.info("Uploading optimizer.db to blob storage…")
            storage.upload_db()
            logger.info("DB blob upload complete.")
        except Exception:
            logger.error("Failed to upload DB blob on shutdown.", exc_info=True)
    logger.info("=== Shutdown complete. ===")


app = FastAPI(
    title="Cloud Cost Optimizer & Remediation Engine",
    version="0.1.0",
    description="FinOps API for Azure — identify waste, generate remediation scripts.",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed = (perf_counter() - start) * 1000
        logger.error(
            "Unhandled exception | %s %s | %.1fms | %s: %s",
            request.method, request.url.path, elapsed,
            type(exc).__name__, exc,
            exc_info=True,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
    elapsed = (perf_counter() - start) * 1000
    level = logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(
        level,
        "%s %s → %d | %.1fms",
        request.method, request.url.path, response.status_code, elapsed,
    )
    return response


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception in %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


# ── API Routers ───────────────────────────────────────────────────────────────
app.include_router(jobs.router)
app.include_router(dashboard.router)
app.include_router(findings.router)
app.include_router(scripts.router)
app.include_router(resources.router)
app.include_router(costs.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    from api.database import SessionLocal
    from api.models import JobRun
    cfg = _gs()
    try:
        db = SessionLocal()
        latest = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
        db.close()
        logger.debug("Health check OK — last job: %s", latest.id if latest else "none")
        return {
            "status": "ok",
            "db_provider": cfg.DATABASE_PROVIDER,
            "last_job_id": latest.id if latest else None,
            "last_job_status": latest.status if latest else None,
        }
    except Exception as exc:
        logger.error("Health check failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": str(exc)},
        )


# ── Serve React dashboard (built static files) ────────────────────────────────
_dashboard_dist = Path(__file__).parent.parent / "dashboard" / "dist"
if _dashboard_dist.exists():
    app.mount("/", StaticFiles(directory=str(_dashboard_dist), html=True), name="dashboard")
    logger.info("Serving React dashboard from %s", _dashboard_dist)