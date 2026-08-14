"""
API key management, for the pharmacy's own administrators.

Issuing a key is the only moment its plaintext exists; everything after that
works from the hash, so the create response is the customer's single chance to
copy it.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status

from dependencies import CurrentUser, DbSession, NotImpersonating, OrgAdminOrAbove
from models.api_key import ApiKeyScope
from models.user import UserRole
from repositories.organization import MembershipRepository
from schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, ApiKeyScopeOut
from services.api_key_service import ApiKeyService
from services.audit_service import AuditService

router = APIRouter(prefix="/api-keys", tags=["API keys"])

SCOPE_LABELS: dict[str, tuple[str, str]] = {
    ApiKeyScope.INVENTORY_READ.value: (
        "قراءة المخزون",
        "الاطلاع على الأصناف والتشغيلات وما يقترب انتهاؤه.",
    ),
    ApiKeyScope.INVENTORY_WRITE.value: (
        "كتابة المخزون",
        "إرسال أصناف جديدة أو تحديث الكميات من نظامك.",
    ),
    ApiKeyScope.LISTINGS_READ.value: (
        "قراءة العروض",
        "الاطلاع على عروضك المنشورة في السوق.",
    ),
}


async def _require_org(current_user, db) -> uuid.UUID:
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="المفاتيح تدار من حساب المنشأة",
        )
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="لا توجد منشأة مرتبطة بالحساب"
        )
    return org_id


@router.get("/scopes", response_model=list[ApiKeyScopeOut])
async def list_scopes(current_user: CurrentUser) -> list[ApiKeyScopeOut]:
    """What a key may be allowed to do, for the creation form."""
    return [
        ApiKeyScopeOut(value=value, label_ar=label, description_ar=description)
        for value, (label, description) in SCOPE_LABELS.items()
    ]


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(current_user: CurrentUser, db: DbSession) -> list[ApiKeyOut]:
    org_id = await _require_org(current_user, db)
    keys = await ApiKeyService(db).list_for_org(org_id)
    return [ApiKeyOut.model_validate(key) for key in keys]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: ApiKeyCreate,
    request: Request,
    current_user: OrgAdminOrAbove,
    db: DbSession,
    # A key is shown once and keeps working long after a support session ends,
    # so issuing one from inside a customer's account would turn a time-limited
    # look at it into permanent access.
    _not_impersonating: NotImpersonating = None,
) -> ApiKeyCreated:
    org_id = await _require_org(current_user, db)
    service = ApiKeyService(db)

    try:
        key, plaintext = await service.create(
            organization_id=org_id,
            created_by_id=current_user.id,
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    await AuditService(db).log(
        action="api_key.create",
        resource_type="api_key",
        resource_id=key.id,
        actor_id=current_user.id,
        organization_id=org_id,
        # The prefix, never the key.
        after_state={"name": key.name, "prefix": key.prefix, "scopes": key.scopes},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(key)

    # The plaintext is not on the model — it exists only here, for this response.
    return ApiKeyCreated(
        **ApiKeyOut.model_validate(key).model_dump(), key=plaintext
    )


@router.delete("/{key_id}", response_model=ApiKeyOut)
async def revoke_key(
    key_id: uuid.UUID,
    request: Request,
    current_user: OrgAdminOrAbove,
    db: DbSession,
) -> ApiKeyOut:
    org_id = await _require_org(current_user, db)
    service = ApiKeyService(db)

    key = await service.get_for_org(key_id, org_id)
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المفتاح غير موجود")
    if not key.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="المفتاح ملغى بالفعل")

    await service.revoke(key, current_user.id)
    await AuditService(db).log(
        action="api_key.revoke",
        resource_type="api_key",
        resource_id=key.id,
        actor_id=current_user.id,
        organization_id=org_id,
        after_state={"prefix": key.prefix},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(key)
    return ApiKeyOut.model_validate(key)
