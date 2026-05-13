"""User repository."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_active(self, id: uuid.UUID) -> User | None:
        result = await self.db.execute(
            select(User).where(
                User.id == id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_reset_token(self, token: str) -> User | None:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(User).where(
                User.password_reset_token == token,
                User.password_reset_expires > now,
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
