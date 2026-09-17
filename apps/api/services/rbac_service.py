"""
Roles, members and invitations for one pharmacy.

The four system roles mirror the legacy membership roles and are created the
first time an organization's team is looked at, so every pharmacy starts with
the same vocabulary. Custom roles are whatever the owner builds on top.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.password import hash_password
from auth.permissions import (
    ALL_KEYS,
    PERMISSIONS,
    SYSTEM_ROLE_NAMES,
    SYSTEM_ROLE_PERMISSIONS,
)
from config import settings
from models.notification import NotificationType
from models.organization import (
    MembershipRole,
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.rbac import InviteStatus, OrgRole, TeamInvite
from models.user import User, UserRole
from repositories.notification import NotificationPreferenceRepository
from repositories.rbac import OrgRoleRepository, TeamInviteRepository, TeamMemberRepository
from repositories.user import UserRepository
from schemas.team import (
    InviteAccept,
    InviteCreate,
    InviteOut,
    InvitePreview,
    MemberOut,
    MemberUpdate,
    PermissionGroupOut,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
)
from services.audit_service import AuditService
from services.notification_service import NotificationService
from services.settings_reader import get_int

INVITE_TTL_KEY = "team.invite_ttl_days"
INVITE_TTL_DEFAULT_DAYS = 7


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def permission_groups() -> list[PermissionGroupOut]:
    """The catalogue in the order it is declared, grouped by screen."""
    groups: dict[str, PermissionGroupOut] = {}
    for p in PERMISSIONS:
        group = groups.get(p.group_ar)
        if group is None:
            group = PermissionGroupOut(group_ar=p.group_ar, group_en=p.group_en, permissions=[])
            groups[p.group_ar] = group
        group.permissions.append(PermissionOut(key=p.key, label_ar=p.label_ar, label_en=p.label_en))
    return list(groups.values())


def _legacy_role_for(role: OrgRole) -> MembershipRole:
    """The membership `role` column a custom role maps onto."""
    if role.is_system:
        try:
            return MembershipRole(role.key)
        except ValueError:
            pass
    return MembershipRole.PHARMACIST


def _user_role_for(role: OrgRole) -> UserRole:
    """The account-level role for someone joining through this org role.

    Anyone who may manage the organization is an org admin at account level,
    which is what the older guards look at; everyone else is a pharmacist or,
    for the read-only system role, a viewer.
    """
    if role.is_system and role.key == MembershipRole.VIEWER.value:
        return UserRole.VIEWER
    if "org.manage" in (role.permissions or []):
        return UserRole.ORG_ADMIN
    return UserRole.PHARMACIST


class RbacService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.roles = OrgRoleRepository(db)
        self.members = TeamMemberRepository(db)
        self.invites = TeamInviteRepository(db)
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    # ── System roles ─────────────────────────────────────────────────────────

    async def ensure_system_roles(self, org_id: uuid.UUID) -> dict[str, OrgRole]:
        """Create the four system roles for an organization if they are missing."""
        existing = {r.key: r for r in await self.roles.list_by_org(org_id) if r.is_system}
        for legacy, keys in SYSTEM_ROLE_PERMISSIONS.items():
            if legacy.value in existing:
                continue
            name_ar, name_en = SYSTEM_ROLE_NAMES[legacy]
            role = OrgRole(
                id=uuid.uuid4(),
                organization_id=org_id,
                key=legacy.value,
                name_ar=name_ar,
                name=name_en,
                is_system=True,
                permissions=sorted(keys),
            )
            self.db.add(role)
            existing[legacy.value] = role
        await self.db.flush()
        return existing

    # ── Roles ────────────────────────────────────────────────────────────────

    async def list_roles(self, org_id: uuid.UUID) -> list[RoleOut]:
        await self.ensure_system_roles(org_id)
        counts = await self.roles.member_counts(org_id)
        # Members without a custom role still count under their legacy role.
        legacy_counts: dict[str, int] = {}
        for membership, _user in await self.members.list_by_org(org_id):
            if membership.role_id is None and membership.is_active:
                key = MembershipRole(membership.role).value
                legacy_counts[key] = legacy_counts.get(key, 0) + 1
        out: list[RoleOut] = []
        for role in await self.roles.list_by_org(org_id):
            count = counts.get(role.id, 0)
            if role.is_system:
                count += legacy_counts.get(role.key, 0)
            item = RoleOut.model_validate(role)
            item.member_count = count
            out.append(item)
        return out

    async def get_role(self, org_id: uuid.UUID, role_id: uuid.UUID) -> RoleOut:
        await self.ensure_system_roles(org_id)
        role = await self._role_or_404(org_id, role_id)
        item = RoleOut.model_validate(role)
        item.member_count = await self._member_count(org_id, role)
        return item

    async def _member_count(self, org_id: uuid.UUID, role: OrgRole) -> int:
        count = await self.roles.count_members(role.id)
        if role.is_system:
            for membership, _user in await self.members.list_by_org(org_id):
                if membership.role_id is None and membership.role == role.key:
                    count += 1
        return count

    async def _role_or_404(self, org_id: uuid.UUID, role_id: uuid.UUID) -> OrgRole:
        role = await self.roles.get_in_org(role_id, org_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الدور غير موجود")
        return role

    @staticmethod
    def _validate_permissions(keys: list[str]) -> list[str]:
        unknown = sorted(set(keys) - ALL_KEYS)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"صلاحيات غير معروفة: {', '.join(unknown)}",
            )
        return sorted(set(keys))

    async def create_role(self, org_id: uuid.UUID, actor: User, data: RoleCreate) -> RoleOut:
        await self.ensure_system_roles(org_id)
        permissions = self._validate_permissions(data.permissions)
        key = f"custom_{uuid.uuid4().hex[:10]}"
        role = OrgRole(
            id=uuid.uuid4(),
            organization_id=org_id,
            key=key,
            name_ar=data.name_ar.strip(),
            name=(data.name or data.name_ar).strip(),
            description_ar=data.description_ar,
            is_system=False,
            permissions=permissions,
        )
        self.db.add(role)
        await self.db.flush()
        await self.audit.log(
            action="role.create",
            resource_type="org_role",
            resource_id=role.id,
            actor_id=actor.id,
            organization_id=org_id,
            after_state={"name_ar": role.name_ar, "permissions": permissions},
        )
        item = RoleOut.model_validate(role)
        item.member_count = 0
        return item

    async def update_role(
        self, org_id: uuid.UUID, actor: User, role_id: uuid.UUID, data: RoleUpdate
    ) -> RoleOut:
        role = await self._role_or_404(org_id, role_id)
        before = {"name_ar": role.name_ar, "permissions": list(role.permissions or [])}

        if data.permissions is not None:
            if role.is_system and role.key == MembershipRole.OWNER.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="دور المالك يحتفظ بجميع الصلاحيات ولا يمكن تعديلها",
                )
            role.permissions = self._validate_permissions(data.permissions)
        if data.name_ar is not None:
            role.name_ar = data.name_ar.strip()
        if data.name is not None:
            role.name = data.name.strip() or role.name_ar
        if data.description_ar is not None:
            role.description_ar = data.description_ar
        await self.db.flush()

        await self.audit.log(
            action="role.update",
            resource_type="org_role",
            resource_id=role.id,
            actor_id=actor.id,
            organization_id=org_id,
            before_state=before,
            after_state={"name_ar": role.name_ar, "permissions": list(role.permissions or [])},
        )
        item = RoleOut.model_validate(role)
        item.member_count = await self._member_count(org_id, role)
        return item

    async def delete_role(self, org_id: uuid.UUID, actor: User, role_id: uuid.UUID) -> None:
        role = await self._role_or_404(org_id, role_id)
        if role.is_system:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="الأدوار الأساسية لا يمكن حذفها",
            )
        if await self.roles.count_members(role.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن حذف دور مرتبط بأعضاء. انقل الأعضاء إلى دور آخر أولا",
            )
        if await self.roles.count_pending_invites(role.id) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن حذف دور له دعوات معلقة. ألغ الدعوات أولا",
            )
        await self.audit.log(
            action="role.delete",
            resource_type="org_role",
            resource_id=role.id,
            actor_id=actor.id,
            organization_id=org_id,
            before_state={"name_ar": role.name_ar, "permissions": list(role.permissions or [])},
        )
        await self.roles.delete(role)

    # ── Members ──────────────────────────────────────────────────────────────

    async def list_members(self, org_id: uuid.UUID, actor: User) -> list[MemberOut]:
        system = await self.ensure_system_roles(org_id)
        out: list[MemberOut] = []
        for membership, user in await self.members.list_by_org(org_id):
            role = membership.custom_role
            if role is None:
                role = system.get(MembershipRole(membership.role).value)
            out.append(
                MemberOut(
                    id=membership.id,
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    phone=user.phone,
                    role_id=membership.role_id,
                    role_key=role.key if role else membership.role,
                    role_name_ar=role.name_ar if role else membership.role,
                    is_active=membership.is_active and user.is_active,
                    is_self=user.id == actor.id,
                    joined_at=membership.joined_at,
                    last_login_at=user.last_login_at,
                )
            )
        return out

    async def update_member(
        self, org_id: uuid.UUID, actor: User, membership_id: uuid.UUID, data: MemberUpdate
    ) -> MemberOut:
        await self.ensure_system_roles(org_id)
        membership = await self.members.get_in_org(membership_id, org_id)
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العضو غير موجود")

        before = {
            "role_id": membership.role_id,
            "role": membership.role,
            "is_active": membership.is_active,
        }
        was_owner = await self._is_owner(membership)
        is_self = membership.user_id == actor.id

        if data.role_id is not None and data.role_id != membership.role_id:
            role = await self._role_or_404(org_id, data.role_id)
            demoting_owner = was_owner and role.key != MembershipRole.OWNER.value
            if demoting_owner and await self._is_last_owner(org_id, membership):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="لا يمكن تغيير دور المالك الوحيد للمنشأة",
                )
            membership.role_id = role.id
            membership.role = _legacy_role_for(role)
            # Keep the account-level role in step so older guards agree.
            user = await self.db.get(User, membership.user_id)
            if user is not None and user.role != UserRole.SUPER_ADMIN:
                user.role = _user_role_for(role)

        if data.is_active is not None and data.is_active != membership.is_active:
            if not data.is_active:
                if is_self:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="لا يمكنك تعطيل عضويتك بنفسك",
                    )
                if was_owner and await self._is_last_owner(org_id, membership):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="لا يمكن تعطيل المالك الوحيد للمنشأة",
                    )
            membership.is_active = data.is_active

        await self.db.flush()
        await self.audit.log(
            action="member.update",
            resource_type="membership",
            resource_id=membership.id,
            actor_id=actor.id,
            organization_id=org_id,
            before_state=before,
            after_state={
                "role_id": membership.role_id,
                "role": membership.role,
                "is_active": membership.is_active,
            },
        )
        await self.db.refresh(membership)
        members = await self.list_members(org_id, actor)
        return next(m for m in members if m.id == membership.id)

    async def _is_owner(self, membership: UserOrganizationMembership) -> bool:
        if membership.role_id is not None:
            role = membership.custom_role or await self.db.get(OrgRole, membership.role_id)
            return role is not None and role.is_system and role.key == MembershipRole.OWNER.value
        return membership.role == MembershipRole.OWNER

    async def _is_last_owner(
        self, org_id: uuid.UUID, membership: UserOrganizationMembership
    ) -> bool:
        owners = await self.members.list_owners(org_id)
        return all(o.id == membership.id for o in owners)

    # ── Invites ──────────────────────────────────────────────────────────────

    def _invite_out(self, invite: TeamInvite) -> InviteOut:
        return InviteOut(
            id=invite.id,
            email=invite.email,
            full_name=invite.full_name,
            role_id=invite.role_id,
            role_name_ar=invite.role.name_ar if invite.role else "",
            invited_by_name=invite.invited_by.full_name if invite.invited_by else None,
            status=self._effective_status(invite),
            expires_at=invite.expires_at,
            accepted_at=invite.accepted_at,
            created_at=invite.created_at,
        )

    @staticmethod
    def _effective_status(invite: TeamInvite) -> InviteStatus:
        if (
            invite.status == InviteStatus.PENDING
            and invite.expires_at <= datetime.now(timezone.utc)
        ):
            return InviteStatus.EXPIRED
        return InviteStatus(invite.status)

    async def list_invites(self, org_id: uuid.UUID) -> list[InviteOut]:
        return [self._invite_out(i) for i in await self.invites.list_by_org(org_id)]

    async def create_invite(
        self, org_id: uuid.UUID, actor: User, data: InviteCreate
    ) -> tuple[InviteOut, str]:
        await self.ensure_system_roles(org_id)
        role = await self._role_or_404(org_id, data.role_id)
        email = data.email.lower()

        existing_user = await self.users.get_by_email(email)
        if existing_user is not None:
            if existing_user.role == UserRole.SUPER_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="لا يمكن دعوة هذا البريد",
                )
            current = await self.members.get_any_by_user_and_org(existing_user.id, org_id)
            if current is not None and current.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="هذا البريد عضو في المنشأة بالفعل",
                )
        pending = await self.invites.get_pending_for_email(org_id, email)
        if pending is not None and pending.expires_at > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="توجد دعوة معلقة لهذا البريد. ألغها أولا لإرسال دعوة جديدة",
            )

        # Seats are active members plus outstanding invitations — an invite is a
        # reserved seat, so it counts against the plan cap before it is accepted.
        from sqlalchemy import func, select

        from services.entitlement_service import EntitlementService

        seats = int(
            await self.db.scalar(
                select(func.count(UserOrganizationMembership.id)).where(
                    UserOrganizationMembership.organization_id == org_id,
                    UserOrganizationMembership.is_active.is_(True),
                )
            )
            or 0
        ) + int(
            await self.db.scalar(
                select(func.count(TeamInvite.id)).where(
                    TeamInvite.organization_id == org_id,
                    TeamInvite.status == InviteStatus.PENDING,
                )
            )
            or 0
        )
        await EntitlementService(self.db).check_resource_limit(org_id, "max_team_members", seats)

        ttl_days = await get_int(self.db, INVITE_TTL_KEY, INVITE_TTL_DEFAULT_DAYS)
        token = secrets.token_urlsafe(32)
        invite = TeamInvite(
            id=uuid.uuid4(),
            organization_id=org_id,
            email=email,
            full_name=(data.full_name or "").strip() or None,
            role_id=role.id,
            invited_by_id=actor.id,
            token_hash=hash_invite_token(token),
            status=InviteStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=max(1, ttl_days)),
        )
        self.db.add(invite)
        await self.db.flush()
        await self.db.refresh(invite)

        organization = await self.db.get(PharmacyOrganization, org_id)
        org_name = (organization.name_ar or organization.name) if organization else ""
        link = self._invite_link(token)

        from services.integrations.email_service import email_service, team_invite_email

        subject, text, html = team_invite_email(org_name, actor.full_name, link, role.name_ar)
        await email_service.send(email, subject, text, html)

        await self.audit.log(
            action="team.invite",
            resource_type="team_invite",
            resource_id=invite.id,
            actor_id=actor.id,
            organization_id=org_id,
            after_state={"email": email, "role_id": role.id, "expires_at": invite.expires_at},
        )
        return self._invite_out(invite), link

    @staticmethod
    def _invite_link(token: str) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/ar/invite/{token}"

    async def revoke_invite(self, org_id: uuid.UUID, actor: User, invite_id: uuid.UUID) -> None:
        invite = await self.invites.get_in_org(invite_id, org_id)
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الدعوة غير موجودة")
        if invite.status != InviteStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن إلغاء دعوة غير معلقة",
            )
        invite.status = InviteStatus.REVOKED
        await self.db.flush()
        await self.audit.log(
            action="team.invite_revoke",
            resource_type="team_invite",
            resource_id=invite.id,
            actor_id=actor.id,
            organization_id=org_id,
            after_state={"email": invite.email},
        )

    async def _pending_invite_by_token(self, token: str) -> TeamInvite:
        invite = await self.invites.get_by_token_hash(hash_invite_token(token))
        if invite is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="رابط الدعوة غير صالح",
            )
        effective = self._effective_status(invite)
        if effective == InviteStatus.EXPIRED:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="انتهت صلاحية الدعوة. اطلب دعوة جديدة من مدير المنشأة",
            )
        if effective == InviteStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="تم قبول هذه الدعوة مسبقا. سجل الدخول بحسابك",
            )
        if effective == InviteStatus.REVOKED:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="تم إلغاء هذه الدعوة",
            )
        return invite

    async def preview_invite(self, token: str) -> InvitePreview:
        invite = await self._pending_invite_by_token(token)
        organization = await self.db.get(PharmacyOrganization, invite.organization_id)
        existing = await self.users.get_by_email(invite.email)
        return InvitePreview(
            org_name=(organization.name_ar or organization.name) if organization else "",
            role_name_ar=invite.role.name_ar if invite.role else "",
            email=invite.email,
            full_name=invite.full_name,
            expires_at=invite.expires_at,
            status=InviteStatus.PENDING,
            existing_account=existing is not None,
        )

    async def accept_invite(self, data: InviteAccept) -> tuple[User, bool]:
        """Create (or attach) the account behind an invitation.

        Returns the user and whether the account already existed — an existing
        account keeps its password and signs in as usual.
        """
        invite = await self._pending_invite_by_token(data.token)
        role = invite.role or await self.db.get(OrgRole, invite.role_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="الدور المرتبط بالدعوة لم يعد موجودا",
            )

        user = await self.users.get_by_email(invite.email)
        existed = user is not None
        if user is None:
            if not data.password:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="كلمة المرور مطلوبة لإنشاء الحساب",
                )
            full_name = (data.full_name or invite.full_name or "").strip()
            if len(full_name) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="الاسم الكامل مطلوب",
                )
            user = User(
                id=uuid.uuid4(),
                email=invite.email,
                full_name=full_name,
                hashed_password=hash_password(data.password),
                role=_user_role_for(role),
                is_active=True,
                is_email_verified=True,
                email_verified_at=datetime.now(timezone.utc),
            )
            self.db.add(user)
            await self.db.flush()
            await NotificationPreferenceRepository(self.db).ensure_defaults(user.id)
        elif not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="الحساب معطل — تواصل مع الدعم",
            )

        membership = await self.members.get_any_by_user_and_org(user.id, invite.organization_id)
        if membership is None:
            membership = UserOrganizationMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                organization_id=invite.organization_id,
                role=_legacy_role_for(role),
                role_id=role.id,
                is_active=True,
                joined_at=datetime.now(timezone.utc),
            )
            self.db.add(membership)
        else:
            membership.role = _legacy_role_for(role)
            membership.role_id = role.id
            membership.is_active = True
            membership.joined_at = membership.joined_at or datetime.now(timezone.utc)

        invite.status = InviteStatus.ACCEPTED
        invite.accepted_at = datetime.now(timezone.utc)
        await self.db.flush()

        await self.audit.log(
            action="team.invite_accept",
            resource_type="team_invite",
            resource_id=invite.id,
            actor_id=user.id,
            organization_id=invite.organization_id,
            after_state={"email": invite.email, "role_id": role.id, "user_id": user.id},
        )

        organization = await self.db.get(PharmacyOrganization, invite.organization_id)
        org_name = (organization.name_ar or organization.name) if organization else ""
        notifications = NotificationService(self.db)
        for owner in await self.members.list_owners(invite.organization_id):
            if owner.user_id == user.id:
                continue
            await notifications.create(
                user_id=owner.user_id,
                notification_type=NotificationType.TEAM_MEMBER_JOINED,
                title=f"{user.full_name} joined the team",
                title_ar=f"انضم {user.full_name} إلى الفريق",
                body=f"{user.full_name} accepted the invitation to {org_name} as {role.name}.",
                body_ar=f"قبل {user.full_name} الدعوة للانضمام إلى {org_name} بدور {role.name_ar}.",
                organization_id=invite.organization_id,
                resource_type="membership",
                resource_id=membership.id,
            )
        return user, existed
