"""
Reading a platform setting at runtime.

The admin owns these numbers, so a service must read them when it acts rather
than bake them in — but a malformed row must never stop a sale, a renewal or a
payout. Every reader here falls back to the caller's default and logs why.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.settings import PlatformSettings
from services.settings_catalog import unwrap

logger = logging.getLogger("api.settings")


async def get_setting(db: AsyncSession, key: str, default: object = None) -> object:
    row = (
        await db.execute(select(PlatformSettings).where(PlatformSettings.key == key))
    ).scalar_one_or_none()
    if row is None:
        return default
    value = unwrap(row.value)
    if value is None:
        value = row.value_text
    return default if value is None else value


async def get_decimal(
    db: AsyncSession,
    key: str,
    default: Decimal,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal:
    raw = await get_setting(db, key, None)
    if raw is None:
        return default
    try:
        if isinstance(raw, bool):  # bool is an int subclass — reject it explicitly
            raise TypeError
        value = Decimal(str(raw))
    except (TypeError, ValueError, InvalidOperation):
        logger.warning("%s is not a number (%r) — using %s", key, raw, default)
        return default
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        logger.warning("%s out of range (%s) — using %s", key, value, default)
        return default
    return value


async def get_int(db: AsyncSession, key: str, default: int) -> int:
    value = await get_decimal(db, key, Decimal(default))
    return int(value)


async def get_bool(db: AsyncSession, key: str, default: bool) -> bool:
    raw = await get_setting(db, key, None)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {"true", "1", "yes", "on"}
    if isinstance(raw, (int, float)):
        return bool(raw)
    return default


async def get_dict(db: AsyncSession, key: str, default: dict) -> dict:
    raw = await get_setting(db, key, None)
    return raw if isinstance(raw, dict) else default
