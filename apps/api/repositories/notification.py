"""Notification repository."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.notification import Notification, NotificationPreference
from repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Notification, db)

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Notification], int]:
        clauses = [Notification.user_id == user_id]
        if unread_only:
            clauses.append(Notification.is_read.is_(False))
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def count_unread(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one()

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import update
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        return result.rowcount


class NotificationPreferenceRepository(BaseRepository[NotificationPreference]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(NotificationPreference, db)

    async def list_by_user(
        self, user_id: uuid.UUID
    ) -> Sequence[NotificationPreference]:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        )
        return result.scalars().all()

    async def ensure_defaults(self, user_id: uuid.UUID) -> Sequence[NotificationPreference]:
        """Create the default preference set once, then return the user's rows.

        Called on registration and again lazily on first read, so accounts that
        pre-date this still get a populated preferences screen.
        """
        from models.notification import NotificationChannel, NotificationType

        existing = await self.list_by_user(user_id)
        if existing:
            return existing

        # WhatsApp is not implemented yet, so it is not offered as a choice.
        channels = (NotificationChannel.IN_APP, NotificationChannel.EMAIL)
        rows = [
            NotificationPreference(
                id=uuid.uuid4(),
                user_id=user_id,
                notification_type=ntype,
                channel=channel,
                is_enabled=True,
            )
            for ntype in NotificationType
            for channel in channels
        ]
        self.db.add_all(rows)
        await self.db.flush()
        return rows
