"""
FastAPI application entrypoint.

Configures CORS, mounts the v1 API router, and provides a health endpoint.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import init_db, close_db, check_db_health
from app.api.v1.datasets.router import router as datasets_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    settings = get_settings()

    # Ensure the upload directory exists
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)

    # Initialize async database engine
    init_db(settings)

    yield

    # Cleanly dispose database connection pool
    await close_db()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Pandas-Stat Statistical Engine",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow the Next.js frontend to call the engine
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────
    app.include_router(datasets_router)

    # ── Health endpoint ─────────────────────────────────────────────
    @app.get("/api/v1/health")
    async def health():
        db_ok = await check_db_health()
        return {
            "status": "ok" if db_ok else "degraded",
            "version": settings.app_version,
            "database": "connected" if db_ok else "disconnected",
        }

    return app


app = create_app()
