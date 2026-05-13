"""
Auth service — registration, login, token refresh, password management.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import create_access_token, create_refresh_token, decode_token
from auth.password import hash_password, verify_password
from models.branch import StorageConditionStatus
from models.organization import MembershipRole, OrganizationStatus, PharmacyOrganization, UserOrganizationMembership
from models.branch import PharmacyBranch
from models.inventory import NearExpiryRule
from models.user import User, UserRole
from repositories.organization import MembershipRepository, OrganizationRepository
from repositories.user import UserRepository
from schemas.auth import LoginRequest, LoginResponse, RegisterRequest, RefreshResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.membership_repo = MembershipRepository(db)

    async def register(self, data: RegisterRequest) -> User:
        # Check duplicate email
        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # Check duplicate org CR
        existing_org = await self.org_repo.get_by_cr(data.commercial_registration_number)
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization with this CR number already exists",
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

        await self.db.flush()
        return user

    async def login(self, data: LoginRequest) -> LoginResponse:
        user = await self.user_repo.get_by_email(data.email.lower())
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )

        # Get org_id
        org_id = await self.membership_repo.get_user_org_id(user.id)

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

    async def forgot_password(self, email: str) -> str:
        user = await self.user_repo.get_by_email(email.lower())
        if not user:
            # Return silently to avoid email enumeration
            return ""
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await self.db.flush()
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        user = await self.user_repo.get_by_reset_token(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )
        user.hashed_password = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        await self.db.flush()
