"""Admin router — approvals queue, moderation, settings, audit logs."""
from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, HTTPException, Request

from dependencies import DbSession, SuperAdmin
from models.organization import OrganizationStatus
from repositories.audit import AuditLogRepository
from repositories.organization import OrganizationRepository
from repositories.marketplace import ListingRepository
from models.marketplace import ListingStatus
from schemas.common import PaginatedResponse
from schemas.organization import OrganizationOut

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/approvals", response_model=PaginatedResponse[OrganizationOut])
async def list_pending_approvals(
    db: DbSession,
    current_user: SuperAdmin,
    page: int = 1,
    page_size: int = 20,
):
    repo = OrganizationRepository(db)
    rows, total = await repo.list_by_status(
        status=OrganizationStatus.PENDING,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse(
        items=[OrganizationOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/compliance", response_model=PaginatedResponse[OrganizationOut])
async def list_compliance_review(
    db: DbSession,
    current_user: SuperAdmin,
    page: int = 1,
    page_size: int = 20,
):
    from sqlalchemy import select
    from models.organization import PharmacyOrganization
    from models.branch import PharmacyBranch, StorageConditionStatus

    result = await db.execute(
        select(PharmacyOrganization).where(
            PharmacyOrganization.deleted_at.is_(None),
            PharmacyOrganization.status == OrganizationStatus.APPROVED,
        ).offset((page - 1) * page_size).limit(page_size)
    )
    orgs = result.scalars().all()
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).where(
            PharmacyOrganization.deleted_at.is_(None),
            PharmacyOrganization.status == OrganizationStatus.APPROVED,
        )
    )
    total = count_result.scalar_one()
    return PaginatedResponse(
        items=[OrganizationOut.model_validate(r) for r in orgs],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/audit-logs")
async def list_audit_logs(
    db: DbSession,
    current_user: SuperAdmin,
    action: str | None = None,
    resource_type: str | None = None,
    org_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
):
    repo = AuditLogRepository(db)
    rows, total = await repo.list_filtered(
        org_id=org_id, action=action, resource_type=resource_type,
        offset=(page - 1) * page_size, limit=page_size,
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "actor_id": str(r.actor_id) if r.actor_id else None,
                "organization_id": str(r.organization_id) if r.organization_id else None,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": str(r.resource_id) if r.resource_id else None,
                "before_state": r.before_state,
                "after_state": r.after_state,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/moderation")
async def list_moderation_queue(
    db: DbSession,
    current_user: SuperAdmin,
    page: int = 1,
    page_size: int = 20,
):
    repo = ListingRepository(db)
    rows, total = await repo.list_active(
        status=ListingStatus.ACTIVE,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    from schemas.marketplace import ListingOut
    return PaginatedResponse(
        items=[ListingOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/settings")
async def list_settings(db: DbSession, current_user: SuperAdmin):
    from sqlalchemy import select
    from models.settings import PlatformSettings
    result = await db.execute(select(PlatformSettings).order_by(PlatformSettings.category))
    settings = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "key": s.key,
            "value": s.value,
            "value_text": s.value_text,
            "description": s.description,
            "category": s.category,
            "updated_at": s.updated_at.isoformat(),
        }
        for s in settings
    ]


@router.put("/settings/{key}")
async def upsert_setting(
    key: str,
    value: dict,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    from sqlalchemy import select
    from models.settings import PlatformSettings
    from services.audit_service import AuditService

    result = await db.execute(select(PlatformSettings).where(PlatformSettings.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        before = {"value": setting.value}
        setting.value = value.get("value")
        setting.value_text = value.get("value_text")
        setting.updated_by_id = current_user.id
    else:
        setting = PlatformSettings(
            id=uuid.uuid4(),
            key=key,
            value=value.get("value"),
            value_text=value.get("value_text"),
            description=value.get("description"),
            category=value.get("category", "general"),
            updated_by_id=current_user.id,
        )
        db.add(setting)
        before = None

    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="admin_setting_change",
        resource_type="platform_settings",
        resource_id=setting.id,
        actor_id=current_user.id,
        before_state=before,
        after_state={"key": key, "value": setting.value},
        ip_address=request.client.host if request.client else None,
    )

    return {"id": str(setting.id), "key": setting.key, "value": setting.value}
