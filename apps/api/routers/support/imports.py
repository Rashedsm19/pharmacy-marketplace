"""Support console — acting for the customer."""
from __future__ import annotations


import uuid

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select

from dependencies import DbSession, SuperAdmin
from models.branch import PharmacyBranch
from models.organization import (
    PharmacyOrganization,
    UserOrganizationMembership,
)
from models.user import User
from services.audit_service import AuditService

from routers.support.helpers import _client

router = APIRouter()


# ── Acting for the customer ───────────────────────────────────────────────────

@router.post(
    "/organizations/{org_id}/imports",
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_for_customer(
    org_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: SuperAdmin,
    reason: str = Query(min_length=5, max_length=500),
    file: UploadFile = File(...),
) -> dict:
    """Upload an inventory file into a customer's stock on their behalf.

    The processor takes the organization from the job row and does no
    authorization of its own, which means the only thing that has to be right is
    the id written here. Everything else — the worker, the matching, the error
    reporting — is the customer's own path, untouched.
    """
    from config import settings
    from models.import_job import ImportJob, ImportSource, ImportStatus
    from models.notification import NotificationType
    from services.import_service import count_org_items
    from services.notification_service import NotificationService
    from services.integrations.storage_service import storage_service

    organization = await db.get(PharmacyOrganization, org_id)
    if organization is None or organization.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="المنشأة غير موجودة"
        )

    # The processor needs somewhere to put the stock; refuse here rather than
    # queue a job that is guaranteed to fail.
    has_branch = await db.scalar(
        select(PharmacyBranch.id).where(
            PharmacyBranch.organization_id == org_id,
            PharmacyBranch.deleted_at.is_(None),
        )
    )
    if has_branch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="لا يوجد فرع مسجل للمنشأة — أضف فرعا قبل الاستيراد",
        )

    used = await count_org_items(db, org_id)
    if used >= settings.MAX_INVENTORY_ITEMS_PER_ORG:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"بلغ مخزون المنشأة الحد الأقصى ({settings.MAX_INVENTORY_ITEMS_PER_ORG} صنف)",
        )

    stored_path, size = await storage_service.save_import_file(file, org_id)
    filename = (file.filename or "support-upload.xlsx")[:255]

    job = ImportJob(
        id=uuid.uuid4(),
        organization_id=org_id,
        created_by_id=current_user.id,
        filename=filename,
        stored_path=stored_path,
        source=ImportSource.CSV if filename.lower().endswith(".csv") else ImportSource.EXCEL,
        status=ImportStatus.QUEUED,
    )
    db.add(job)
    await db.flush()

    # The customer's stock is about to change. Telling them is not optional:
    # a re-upload overwrites quantities, and silently rewriting a pharmacy's
    # numbers is how a customer relationship ends.
    owners = (
        await db.execute(
            select(User)
            .join(
                UserOrganizationMembership,
                UserOrganizationMembership.user_id == User.id,
            )
            .where(
                UserOrganizationMembership.organization_id == org_id,
                UserOrganizationMembership.is_active.is_(True),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for owner in owners:
        try:
            await NotificationService(db).create(
                user_id=owner.id,
                organization_id=org_id,
                notification_type=NotificationType.SYSTEM,
                title="Support uploaded an inventory file to your account",
                title_ar="رفع فريق الدعم ملف مخزون إلى حسابكم",
                body=f"File: {filename}",
                body_ar=f"الملف: {filename}. السبب: {reason}",
                resource_type="import_job",
                resource_id=job.id,
            )
        except Exception:
            pass

    await AuditService(db).log(
        action="support.inventory.import",
        resource_type="import_job",
        resource_id=job.id,
        actor_id=current_user.id,
        organization_id=org_id,
        after_state={"filename": filename, "size_bytes": size},
        notes=reason,
        **_client(request),
    )
    await db.commit()
    return {
        "id": str(job.id),
        "organization_id": str(org_id),
        "organization_name": organization.name_ar or organization.name,
        "status": "queued",
        "message": "أدرج الملف في طابور المعالجة وأبلغ العميل",
    }

