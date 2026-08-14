"""
Auth service — registration, login, token refresh, password management.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import create_access_token, create_refresh_token, decode_token
from auth.password import hash_password, verify_password
from models.branch import StorageConditionStatus
from models.organization import MembershipRole, OrganizationStatus, PharmacyOrganization, UserOrganizationMembership
from models.branch import PharmacyBranch
from models.inventory import NearExpiryRule
from models.user import User, UserRole
from config import settings
from repositories.notification import NotificationPreferenceRepository
from repositories.organization import MembershipRepository, OrganizationRepository
from repositories.user import UserRepository, hash_reset_token
from schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RefreshResponse
from services.email_service import email_service, password_reset_email

logger = logging.getLogger("api.auth")

# An organization in one of these states cannot be signed into. The message says
# which, because "الحساب معطل" for a pharmacy still awaiting approval would send
# the customer to support for nothing.
_BLOCKED_STATUSES: dict[OrganizationStatus, str] = {
    OrganizationStatus.SUSPENDED: "حساب المنشأة موقوف — تواصل مع الدعم",
    OrganizationStatus.REJECTED: "تم رفض طلب تسجيل المنشأة — تواصل مع الدعم",
}


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.membership_repo = MembershipRepository(db)

    async def register(self, data: RegisterRequest) -> User:
        # Duplicate checks look past soft-deletes on purpose: the UNIQUE constraints
        # do not ignore deleted rows, so a soft-deleted match would still collide.
        if await self.user_repo.email_exists(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="هذا البريد الإلكتروني مسجل مسبقا",
            )

        if await self.org_repo.cr_exists(data.commercial_registration_number):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="رقم السجل التجاري مسجل مسبقا لمنشأة أخرى",
            )

        if data.license_number and await self.org_repo.license_exists(data.license_number):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="رقم الترخيص مسجل مسبقا لمنشأة أخرى",
            )

        # Create org
        org = PharmacyOrganization(
            id=uuid.uuid4(),
            name=data.org_name,
            name_ar=data.org_name_ar,
            commercial_registration_number=data.commercial_registration_number,
            license_number=data.license_number,
            email=data.org_email,
            phone=data.org_phone,
            address=data.org_address,
            city=data.org_city,
            region=data.org_region,
            status=OrganizationStatus.PENDING,
        )
        self.db.add(org)
        await self.db.flush()

        # Create user
        user = User(
            id=uuid.uuid4(),
            email=data.email.lower(),
            phone=data.phone,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=UserRole.ORG_ADMIN,
        )
        self.db.add(user)
        await self.db.flush()

        # Create membership
        membership = UserOrganizationMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            organization_id=org.id,
            role=MembershipRole.OWNER,
            is_active=True,
            joined_at=datetime.now(timezone.utc),
        )
        self.db.add(membership)

        # Create first branch
        branch = PharmacyBranch(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=data.branch_name,
            name_ar=data.branch_name_ar,
            address=data.branch_address,
            city=data.branch_city,
            phone=data.branch_phone,
            storage_condition_status=StorageConditionStatus.UNKNOWN,
        )
        self.db.add(branch)

        # Create default near-expiry rules
        rule = NearExpiryRule(
            id=uuid.uuid4(),
            organization_id=org.id,
        )
        self.db.add(rule)

        # Default notification preferences, so the account starts with a populated
        # preferences screen rather than an empty one.
        await NotificationPreferenceRepository(self.db).ensure_defaults(user.id)

        try:
            await self.db.flush()
        except IntegrityError as exc:
            # Last line of defence: a race between two registrations, or a constraint
            # the checks above don't cover. Never surface this as a bare 500.
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="تعذر إتمام التسجيل — تحقق من أن البريد ورقم السجل التجاري ورقم الترخيص غير مستخدمة",
            ) from exc
        return user

    async def login(self, data: LoginRequest) -> LoginResponse:
        user = await self.user_repo.get_by_email(data.email.lower())
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                # Deliberately the same message for an unknown address and a wrong
                # password: telling them apart is how an attacker learns which
                # emails are registered.
                detail="البريد الإلكتروني أو كلمة المرور غير صحيحة",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="الحساب معطل — تواصل مع الدعم",
            )

        # Get org_id
        org_id = await self.membership_repo.get_user_org_id(user.id)

        # Suspending an organization has to mean something. Until now the status
        # was checked only when issuing an API key and when creating a listing,
        # so a suspended pharmacy's staff could still sign in, browse and bid —
        # the suspension was close to cosmetic.
        if org_id is not None and user.role != UserRole.SUPER_ADMIN:
            organization = await self.db.get(PharmacyOrganization, org_id)
            if organization is not None and organization.status in _BLOCKED_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_BLOCKED_STATUSES[organization.status],
                )

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        access_token = create_access_token(user.id, user.email, user.role, org_id)
        refresh_token = create_refresh_token(user.id, user.email, user.role)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user.id,
            role=user.role,
            org_id=org_id,
        )

    async def refresh(self, refresh_token: str) -> RefreshResponse:
        import jwt
        try:
            token_data = decode_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if token_data.token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        user = await self.user_repo.get_active(uuid.UUID(token_data.sub))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        org_id = await self.membership_repo.get_user_org_id(user.id)
        access_token = create_access_token(user.id, user.email, user.role, org_id)
        return RefreshResponse(access_token=access_token)

    async def issue_password_reset(
        self, user: User, *, ttl_minutes: int = 60, send_email: bool = True
    ) -> tuple[str, datetime, bool]:
        """Mint a reset token for an account. Returns (token, expiry, emailed).

        Shared by the customer's own "forgot password" and by support issuing a
        link on their behalf, so there is exactly one implementation of how a
        reset is granted — and one place where its lifetime is decided.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        # Only the digest is stored; the plaintext leaves in the email and in
        # the response, and is never recoverable from the database.
        user.password_reset_token = hash_reset_token(token)
        user.password_reset_expires = expires_at
        await self.db.flush()

        sent = False
        if send_email:
            subject, text, html = password_reset_email(user.full_name, token)
            sent = await email_service.send(user.email, subject, text, html)
            if not sent:
                logger.warning(
                    "Password reset issued for %s but no email was delivered "
                    "(EMAIL_BACKEND=%s)",
                    user.email,
                    settings.EMAIL_BACKEND,
                )
        return token, expires_at, sent

    async def forgot_password(self, email: str) -> str:
        user = await self.user_repo.get_by_email(email.lower())
        if not user:
            # Return silently to avoid email enumeration
            return ""
        token, _, _ = await self.issue_password_reset(user)
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        user = await self.user_repo.get_by_reset_token(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رابط الاستعادة غير صالح أو انتهت صلاحيته — اطلب رابطا جديدا",
            )
        user.hashed_password = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        await self.db.flush()
