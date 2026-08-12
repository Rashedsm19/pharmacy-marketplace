"""
Async SQLAlchemy 2.0 engine + session factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings


# Managed Postgres providers (Neon, Supabase, Aiven, Render external URLs …) hand
# out libpq-style URLs. asyncpg does not accept these as query parameters and
# raises TypeError on connect, so lift them out of the URL here.
_LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "target_session_attrs")


def split_db_url(url: str) -> tuple[str, dict]:
    """Return (url_without_libpq_params, connect_args for asyncpg)."""
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    connect_args: dict = {}

    sslmode = params.pop("sslmode", None)
    if sslmode:
        # asyncpg accepts the same mode names, just under `ssl`
        connect_args["ssl"] = sslmode
    for key in _LIBPQ_ONLY_PARAMS:
        params.pop(key, None)

    cleaned = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment)
    )
    return cleaned, connect_args


DATABASE_URL, CONNECT_ARGS = split_db_url(settings.DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    connect_args=CONNECT_ARGS,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
