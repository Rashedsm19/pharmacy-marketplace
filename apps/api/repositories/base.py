"""
Generic base repository with common CRUD operations.
"""
from __future__ import annotations

import uuid
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get(self, id: uuid.UUID) -> ModelType | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_many(
        self,
        *where_clauses: Any,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[ModelType], int]:
        q = select(self.model).where(*where_clauses)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()
        rows = (await self.db.execute(q.offset(offset).limit(limit))).scalars().all()
        return rows, total

    async def create(self, **kwargs: Any) -> ModelType:
        obj = self.model(**kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelType, **kwargs: Any) -> ModelType:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def soft_delete(self, obj: ModelType) -> ModelType:
        from datetime import datetime, timezone
        obj.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return obj
