"""
FastAPI dependency injectors: DB session, current user, role guards.
"""
from __future__ import annotations

import uuid
from typing import Annotated, AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import TokenData, decode_token
from database import AsyncSessionLocal
from models.user import User, UserRole

_bearer = HTTPBearer(auto_error=False)


# ── Database Session ──────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── Current User ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_data: TokenData = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_data.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    from sqlalchemy import select

    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(token_data.sub),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ── Optional Current User (for public routes with optional auth) ───────────────

async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> User | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


# ── Role Guards ───────────────────────────────────────────────────────────────

def require_role(*roles: UserRole):
    async def _guard(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return _guard


def require_super_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


SuperAdmin = Annotated[User, Depends(require_super_admin)]


def require_org_admin_or_above(current_user: CurrentUser) -> User:
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin access required",
        )
    return current_user


OrgAdminOrAbove = Annotated[User, Depends(require_org_admin_or_above)]


# ── API Key Authentication ────────────────────────────────────────────────────
#
# The external endpoints are called by a customer's own system, which has no
# user and no session. It presents a key in X-API-Key, and what comes back is an
# organization rather than a user — everything downstream is scoped to it
# exactly as a logged-in request would be.

class ApiKeyContext:
    """The authenticated caller behind an API key."""

    def __init__(self, key, organization_id: uuid.UUID, scopes: list[str]) -> None:
        self.key = key
        self.organization_id = organization_id
        self.scopes = scopes

    def has(self, scope: str) -> bool:
        return scope in self.scopes


async def get_api_key_context(request: Request, db: DbSession) -> ApiKeyContext:
    from models.organization import OrganizationStatus, PharmacyOrganization
    from services.api_key_service import ApiKeyService

    presented = request.headers.get("X-API-Key") or ""
    if not presented:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="مفتاح API مطلوب في ترويسة X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    service = ApiKeyService(db)
    key = await service.authenticate(presented)
    if key is None:
        # One message for missing, wrong, expired and revoked alike: which of
        # those it is would tell a guesser whether a key ever existed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="مفتاح API غير صالح أو ملغى",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    organization = await db.get(PharmacyOrganization, key.organization_id)
    if organization is None or organization.status != OrganizationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="المنشأة غير معتمدة أو موقوفة",
        )

    await service.record_use(key, request.client.host if request.client else None)
    return ApiKeyContext(key, key.organization_id, list(key.scopes or []))


ApiKeyAuth = Annotated[ApiKeyContext, Depends(get_api_key_context)]


def require_scope(scope: str):
    """Guard an external endpoint with the scope its key must carry."""

    async def _guard(context: ApiKeyAuth) -> ApiKeyContext:
        if not context.has(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"المفتاح لا يملك صلاحية {scope}",
            )
        return context

    return _guard
