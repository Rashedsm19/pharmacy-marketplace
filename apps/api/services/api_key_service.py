"""
Issuing, checking and revoking API keys.

Verification is the hot path: every external request carries a key, and argon2
is deliberately slow. So the lookup is by the key's public prefix — indexed and
unique enough to find one row — and only that row's hash is verified. Without
the prefix, authenticating one request would mean hashing against every key on
the platform.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.password import hash_password, verify_password
from models.api_key import ApiKey, ApiKeyScope

logger = logging.getLogger("api.apikeys")

# "live" leaves room for a future test key without changing what customers
# already have in their configuration.
KEY_PREFIX = "msk_live_"
SECRET_BYTES = 32
# Enough of the key to identify the row, not enough to be worth stealing.
PREFIX_LENGTH = len(KEY_PREFIX) + 8


def generate_key() -> tuple[str, str]:
    """Returns (full key shown once, public prefix stored alongside the hash)."""
    secret = secrets.token_urlsafe(SECRET_BYTES)
    full = f"{KEY_PREFIX}{secret}"
    return full, full[:PREFIX_LENGTH]


class ApiKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        created_by_id: uuid.UUID | None,
        name: str,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a key and return it with its plaintext — the only time it exists."""
        valid = {scope.value for scope in ApiKeyScope}
        unknown = [scope for scope in scopes if scope not in valid]
        if unknown:
            raise ValueError(f"صلاحيات غير معروفة: {', '.join(unknown)}")
        if not scopes:
            raise ValueError("يجب اختيار صلاحية واحدة على الأقل")

        full, prefix = generate_key()
        key = ApiKey(
            id=uuid.uuid4(),
            organization_id=organization_id,
            created_by_id=created_by_id,
            name=name.strip()[:120] or "مفتاح بلا اسم",
            prefix=prefix,
            key_hash=hash_password(full),
            scopes=list(dict.fromkeys(scopes)),
            expires_at=expires_at,
        )
        self.db.add(key)
        await self.db.flush()
        logger.info("Issued API key %s for org %s", prefix, organization_id)
        return key, full

    async def authenticate(self, presented: str) -> ApiKey | None:
        """Resolve a presented key to its row, or None if it is not usable."""
        if not presented or not presented.startswith(KEY_PREFIX):
            return None

        prefix = presented[:PREFIX_LENGTH]
        candidates = (
            await self.db.execute(select(ApiKey).where(ApiKey.prefix == prefix))
        ).scalars().all()

        for key in candidates:
            if not verify_password(presented, key.key_hash):
                continue
            if not key.is_active or key.revoked_at is not None:
                return None
            if key.expires_at and key.expires_at <= datetime.now(timezone.utc):
                return None
            return key
        return None

    async def record_use(self, key: ApiKey, ip: str | None) -> None:
        key.last_used_at = datetime.now(timezone.utc)
        key.last_used_ip = (ip or "")[:64] or None
        key.request_count = (key.request_count or 0) + 1

    async def revoke(self, key: ApiKey, revoked_by_id: uuid.UUID | None) -> ApiKey:
        key.is_active = False
        key.revoked_at = datetime.now(timezone.utc)
        key.revoked_by_id = revoked_by_id
        await self.db.flush()
        logger.info("Revoked API key %s", key.prefix)
        return key

    async def list_for_org(self, organization_id: uuid.UUID) -> list[ApiKey]:
        return list(
            (
                await self.db.execute(
                    select(ApiKey)
                    .where(ApiKey.organization_id == organization_id)
                    .order_by(ApiKey.created_at.desc())
                )
            ).scalars().all()
        )

    async def get_for_org(
        self, key_id: uuid.UUID, organization_id: uuid.UUID
    ) -> ApiKey | None:
        return (
            await self.db.execute(
                select(ApiKey).where(
                    ApiKey.id == key_id, ApiKey.organization_id == organization_id
                )
            )
        ).scalar_one_or_none()
