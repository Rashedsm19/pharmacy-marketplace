"""Organization and membership repositories."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.organization import (
    OrganizationStatus,
    PharmacyOrganization,
    UserOrganizationMembership,
)
from repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[PharmacyOrganization]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(PharmacyOrganization, db)

    async def get_active(self, id: uuid.UUID) -> PharmacyOrganization | None:
        result = await self.db.execute(
            select(PharmacyOrganization).where(
                PharmacyOrganization.id == id,
                PharmacyOrganization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_cr(self, cr_number: str) -> PharmacyOrganization | None:
        result = await self.db.execute(
            select(PharmacyOrganization).where(
                PharmacyOrganization.commercial_registration_number == cr_number,
                PharmacyOrganization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        status: OrganizationStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[PharmacyOrganization], int]:
        clauses = [PharmacyOrganization.deleted_at.is_(None)]
        if status:
            clauses.append(PharmacyOrganization.status == status)
        return await self.get_many(*clauses, offset=offset, limit=limit)


class MembershipRepository(BaseRepository[UserOrganizationMembership]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(UserOrganizationMembership, db)

    async def get_by_user_and_org(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> UserOrganizationMembership | None:
        result = await self.db.execute(
            select(UserOrganizationMembership).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.organization_id == org_id,
                UserOrganizationMembership.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self, org_id: uuid.UUID
    ) -> Sequence[UserOrganizationMembership]:
        result = await self.db.execute(
            select(UserOrganizationMembership).where(
                UserOrganizationMembership.organization_id == org_id,
                UserOrganizationMembership.is_active.is_(True),
            )
        )
        return result.scalars().all()

    async def get_user_org_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        result = await self.db.execute(
            select(UserOrganizationMembership.organization_id).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.is_active.is_(True),
            ).limit(1)
        )
        return result.scalar_one_or_none()
