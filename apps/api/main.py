"""
FastAPI application factory — Pharmacy Near-Expiry Marketplace API.
"""
from __future__ import annotations

import logging
import os
import sys

# ── uvloop bootstrap (graceful fallback) ─────────────────────────────────────
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from config import settings

# ── Logging configuration ─────────────────────────────────────────────────────
if not settings.NOLOG:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )
else:
    logging.disable(logging.CRITICAL)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # ── App instance ──────────────────────────────────────────────────────
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        default_response_class=ORJSONResponse,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    # ── Middleware stack (order matters — outermost applied first) ─────────
    from middleware.logging import LoggingMiddleware
    from middleware.cloudflare import CloudflareGuardMiddleware
    from middleware.appcheck import AppCheckMiddleware

    app.add_middleware(LoggingMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        CloudflareGuardMiddleware,
        require=settings.REQUIRE_CLOUDFLARE,
    )

    app.add_middleware(
        AppCheckMiddleware,
        require=settings.REQUIRE_APPCHECK,
    )

    # ── Startup / Shutdown ────────────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
        await _run_migrations_if_requested()
        await _seed_if_requested()
        await _start_scheduler()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("Shutting down %s", settings.APP_NAME)
        await _stop_scheduler()
        from httpx_client import close_http_client
        await close_http_client()

    # ── Health endpoint ───────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        return {"status": "ok", "version": settings.APP_VERSION}

    # ── Router registration ───────────────────────────────────────────────
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    from routers.auth import router as auth_router
    from routers.organizations import router as orgs_router
    from routers.branches import router as branches_router
    from routers.products import router as products_router
    from routers.inventory import router as inventory_router
    from routers.listings import router as listings_router
    from routers.offers import router as offers_router
    from routers.reservations import router as reservations_router
    from routers.transactions import router as transactions_router
    from routers.reports import router as reports_router
    from routers.admin import router as admin_router
    from routers.notifications import router as notifications_router

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(orgs_router, prefix=prefix)
    app.include_router(branches_router, prefix=prefix)
    app.include_router(products_router, prefix=prefix)
    app.include_router(inventory_router, prefix=prefix)
    app.include_router(listings_router, prefix=prefix)
    app.include_router(offers_router, prefix=prefix)
    app.include_router(reservations_router, prefix=prefix)
    app.include_router(transactions_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)
    app.include_router(admin_router, prefix=prefix)
    app.include_router(notifications_router, prefix=prefix)


_scheduler = None


async def _run_migrations_if_requested() -> None:
    """Run `alembic upgrade head` on startup if RUN_MIGRATIONS_ON_STARTUP=true.

    Run via subprocess so alembic's own asyncio.run() doesn't collide with the
    server's running event loop.
    """
    if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "").lower() not in {"1", "true", "yes"}:
        return
    import asyncio as _asyncio

    api_dir = os.path.dirname(os.path.abspath(__file__))
    logger.info("Running database migrations on startup")
    proc = await _asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head",
        cwd=api_dir,
        stdout=_asyncio.subprocess.PIPE,
        stderr=_asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        logger.error("Migration failed (exit %d):\n%s", proc.returncode, out.decode(errors="replace"))
        raise RuntimeError(f"alembic upgrade failed with code {proc.returncode}")
    logger.info("Migrations complete:\n%s", out.decode(errors="replace")[-500:])


async def _seed_if_requested() -> None:
    """Run seed script on startup if SEED_ON_STARTUP=true (idempotent — skips if data exists)."""
    if os.getenv("SEED_ON_STARTUP", "").lower() not in {"1", "true", "yes"}:
        return
    try:
        from sqlalchemy import select, func
        from database import AsyncSessionLocal
        from models.user import User

        async with AsyncSessionLocal() as session:
            count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
            if count > 0:
                logger.info("Database already has %d users — skipping seed", count)
                return

        logger.info("Database is empty — running seed script")
        from seeds.seed import seed as seed_fn
        await seed_fn()
        logger.info("Seed complete")
    except Exception as exc:
        logger.warning("Seed failed on startup (non-fatal): %s", exc)


async def _start_scheduler() -> None:
    global _scheduler
    try:
        from scheduler import create_scheduler
        _scheduler = create_scheduler()
        _scheduler.start()
        logger.info("APScheduler started")
    except Exception as exc:
        logger.warning("Scheduler failed to start: %s", exc)


async def _stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
