"""User repository."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from repositories.base import BaseRepository


def hash_reset_token(token: str) -> str:
    """What gets stored for a password-reset token.

    SHA-256 rather than argon2 deliberately: the token is 32 bytes of entropy
    from `secrets`, not a human-chosen password, so there is nothing to brute
    force and the lookup stays a single indexed comparison.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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

    async def email_exists(self, email: str) -> bool:
        """Ignores soft-deletes: the UNIQUE constraint on email does not."""
        result = await self.db.execute(
            select(User.id).where(User.email == email.lower()).limit(1)
        )
        return result.scalar_one_or_none() is not None

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
        """Find the account a reset token belongs to.

        The column holds a SHA-256 digest, not the token: a reset token is a
        temporary password, and anyone who can read the table should not be able
        to take over an account with it. Hashing on lookup means the plaintext
        exists only in the email and in the customer's browser.
        """
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(User).where(
                User.password_reset_token == hash_reset_token(token),
                User.password_reset_expires > now,
                User.deleted_at.is_(None),
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
