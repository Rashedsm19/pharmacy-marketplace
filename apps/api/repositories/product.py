"""Product and product category repositories."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.product import Product, ProductCategory
from repositories.base import BaseRepository


class ProductCategoryRepository(BaseRepository[ProductCategory]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ProductCategory, db)

    async def list_all(self) -> Sequence[ProductCategory]:
        result = await self.db.execute(
            select(ProductCategory).order_by(ProductCategory.sort_order)
        )
        return result.scalars().all()

    async def get_by_code(self, code: str) -> ProductCategory | None:
        result = await self.db.execute(
            select(ProductCategory).where(ProductCategory.code == code)
        )
        return result.scalar_one_or_none()


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Product, db)

    @staticmethod
    def visible_to(org_id: uuid.UUID | None):
        """What one organization may see: the shared catalogue plus its own.

        A private product belongs to the pharmacy that imported it and must not
        leak into anyone else's searches. Passing None (a platform admin) drops
        the restriction.
        """
        if org_id is None:
            return Product.id.is_not(None)  # always true — no restriction
        return or_(
            Product.owner_organization_id.is_(None),
            Product.owner_organization_id == org_id,
        )

    async def list_active(
        self,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
        org_id: uuid.UUID | None = None,
        include_drafts: bool = True,
    ) -> tuple[Sequence[Product], int]:
        clauses = [
            Product.is_active.is_(True),
            Product.deleted_at.is_(None),
            self.visible_to(org_id),
        ]
        if not include_drafts:
            clauses.append(Product.is_draft.is_(False))
        if category_id:
            clauses.append(Product.category_id == category_id)
        if search:
            clauses.append(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.name_ar.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.barcode.ilike(f"%{search}%"),
                )
            )
        return await self.get_many(*clauses, offset=offset, limit=limit)

    async def get_by_sku(self, sku: str, org_id: uuid.UUID | None = None) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.sku == sku,
                Product.deleted_at.is_(None),
                self.visible_to(org_id),
            )
        )
        return result.scalars().first()

    async def list_drafts(
        self, offset: int = 0, limit: int = 50
    ) -> tuple[Sequence[Product], int]:
        """Private products awaiting promotion into the shared catalogue."""
        return await self.get_many(
            Product.is_draft.is_(True),
            Product.deleted_at.is_(None),
            offset=offset,
            limit=limit,
        )
