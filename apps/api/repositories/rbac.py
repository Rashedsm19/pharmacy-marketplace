"""Roles and invitations — the queries behind the team screen."""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.organization import UserOrganizationMembership
from models.rbac import InviteStatus, OrgRole, TeamInvite
from models.user import User
from repositories.base import BaseRepository


class OrgRoleRepository(BaseRepository[OrgRole]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(OrgRole, db)

    async def list_by_org(self, org_id: uuid.UUID) -> Sequence[OrgRole]:
        result = await self.db.execute(
            select(OrgRole)
            .where(OrgRole.organization_id == org_id)
            .order_by(OrgRole.is_system.desc(), OrgRole.created_at.asc())
        )
        return result.scalars().all()

    async def get_in_org(self, role_id: uuid.UUID, org_id: uuid.UUID) -> OrgRole | None:
        result = await self.db.execute(
            select(OrgRole).where(OrgRole.id == role_id, OrgRole.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_key(self, org_id: uuid.UUID, key: str) -> OrgRole | None:
        result = await self.db.execute(
            select(OrgRole).where(OrgRole.organization_id == org_id, OrgRole.key == key)
        )
        return result.scalar_one_or_none()

    async def member_counts(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Members per role id, counting only active memberships."""
        result = await self.db.execute(
            select(
                UserOrganizationMembership.role_id,
                func.count(UserOrganizationMembership.id),
            )
            .where(
                UserOrganizationMembership.organization_id == org_id,
                UserOrganizationMembership.is_active.is_(True),
                UserOrganizationMembership.role_id.is_not(None),
            )
            .group_by(UserOrganizationMembership.role_id)
        )
        return {row[0]: row[1] for row in result.all()}

    async def count_members(self, role_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(UserOrganizationMembership.id)).where(
                UserOrganizationMembership.role_id == role_id
            )
        )
        return result.scalar_one()

    async def count_pending_invites(self, role_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(TeamInvite.id)).where(
                TeamInvite.role_id == role_id, TeamInvite.status == InviteStatus.PENDING
            )
        )
        return result.scalar_one()


class TeamMemberRepository:
    """Memberships joined to their users, for the members tab."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_org(
        self, org_id: uuid.UUID
    ) -> Sequence[tuple[UserOrganizationMembership, User]]:
        result = await self.db.execute(
            select(UserOrganizationMembership, User)
            .join(User, User.id == UserOrganizationMembership.user_id)
            .where(
                UserOrganizationMembership.organization_id == org_id,
                User.deleted_at.is_(None),
            )
            .order_by(UserOrganizationMembership.created_at.asc())
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_in_org(
        self, membership_id: uuid.UUID, org_id: uuid.UUID
    ) -> UserOrganizationMembership | None:
        result = await self.db.execute(
            select(UserOrganizationMembership).where(
                UserOrganizationMembership.id == membership_id,
                UserOrganizationMembership.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_any_by_user_and_org(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> UserOrganizationMembership | None:
        """Active or not — used to decide whether an invite needs a new row."""
        result = await self.db.execute(
            select(UserOrganizationMembership).where(
                UserOrganizationMembership.user_id == user_id,
                UserOrganizationMembership.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_owners(self, org_id: uuid.UUID) -> Sequence[UserOrganizationMembership]:
        """Active members who hold every permission, by system role or legacy role."""
        from models.organization import MembershipRole

        result = await self.db.execute(
            select(UserOrganizationMembership)
            .outerjoin(OrgRole, OrgRole.id == UserOrganizationMembership.role_id)
            .where(
                UserOrganizationMembership.organization_id == org_id,
                UserOrganizationMembership.is_active.is_(True),
                (
                    (OrgRole.key == MembershipRole.OWNER.value)
                    | (
                        UserOrganizationMembership.role_id.is_(None)
                        & (UserOrganizationMembership.role == MembershipRole.OWNER.value)
                    )
                ),
            )
        )
        return result.scalars().all()


class TeamInviteRepository(BaseRepository[TeamInvite]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(TeamInvite, db)

    async def list_by_org(self, org_id: uuid.UUID) -> Sequence[TeamInvite]:
        result = await self.db.execute(
            select(TeamInvite)
            .where(TeamInvite.organization_id == org_id)
            .order_by(TeamInvite.created_at.desc())
        )
        return result.scalars().all()

    async def get_in_org(self, invite_id: uuid.UUID, org_id: uuid.UUID) -> TeamInvite | None:
        result = await self.db.execute(
            select(TeamInvite).where(
                TeamInvite.id == invite_id, TeamInvite.organization_id == org_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> TeamInvite | None:
        result = await self.db.execute(
            select(TeamInvite).where(TeamInvite.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_pending_for_email(self, org_id: uuid.UUID, email: str) -> TeamInvite | None:
        result = await self.db.execute(
            select(TeamInvite).where(
                TeamInvite.organization_id == org_id,
                TeamInvite.email == email.lower(),
                TeamInvite.status == InviteStatus.PENDING,
            )
        )
        return result.scalars().first()
