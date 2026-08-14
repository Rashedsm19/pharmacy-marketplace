"""Organizations router — CRUD + approval workflow."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pathlib import Path

from fastapi import Response

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove, SuperAdmin
from models.user import UserRole
from repositories.organization import MembershipRepository, OrganizationRepository
from schemas.common import MessageResponse, PaginatedResponse
from schemas.organization import (
    OrganizationApprove,
    OrganizationOut,
    OrganizationReject,
    OrganizationSuspend,
    OrganizationUpdate,
)
from services.audit_service import AuditService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/me", response_model=OrganizationOut)
async def get_my_organization(db: DbSession, current_user: CurrentUser):
    from repositories.organization import MembershipRepository
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organization found")
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationOut.model_validate(org)


@router.patch("/me", response_model=OrganizationOut)
async def update_my_organization(
    data: OrganizationUpdate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    from repositories.organization import MembershipRepository
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No organization found")
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    update_data = data.model_dump(exclude_unset=True)
    before_state = {k: getattr(org, k) for k in update_data if hasattr(org, k)}
    for k, v in update_data.items():
        if hasattr(org, k):
            setattr(org, k, v)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="organization_updated",
        resource_type="pharmacy_organization",
        resource_id=org.id,
        actor_id=current_user.id,
        organization_id=org.id,
        before_state=before_state,
        after_state=update_data,
        ip_address=request.client.host if request.client else None,
    )
    return OrganizationOut.model_validate(org)


@router.get("", response_model=PaginatedResponse[OrganizationOut])
async def list_organizations(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
):
    repo = OrganizationRepository(db)
    if current_user.role == UserRole.SUPER_ADMIN:
        rows, total = await repo.list_by_status(offset=(page - 1) * page_size, limit=page_size)
    else:
        from repositories.organization import MembershipRepository
        mem_repo = MembershipRepository(db)
        org_id = await mem_repo.get_user_org_id(current_user.id)
        if not org_id:
            return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, pages=0)
        org = await repo.get_active(org_id)
        rows = [org] if org else []
        total = len(rows)

    import math
    return PaginatedResponse(
        items=[OrganizationOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{org_id}", response_model=OrganizationOut)
async def get_organization(org_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    # Non-admins can only view their own org
    if current_user.role != UserRole.SUPER_ADMIN:
        from repositories.organization import MembershipRepository
        mem_repo = MembershipRepository(db)
        user_org = await mem_repo.get_user_org_id(current_user.id)
        if user_org != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return OrganizationOut.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationOut)
async def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
):
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if current_user.role != UserRole.SUPER_ADMIN:
        from repositories.organization import MembershipRepository
        mem_repo = MembershipRepository(db)
        user_org = await mem_repo.get_user_org_id(current_user.id)
        if user_org != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    update_data = data.model_dump(exclude_unset=True)
    before_state = {k: getattr(org, k) for k in update_data if hasattr(org, k)}
    for k, v in update_data.items():
        if hasattr(org, k):
            setattr(org, k, v)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="organization_updated",
        resource_type="pharmacy_organization",
        resource_id=org.id,
        actor_id=current_user.id,
        organization_id=org.id,
        before_state=before_state,
        after_state=update_data,
        ip_address=request.client.host if request.client else None,
    )
    return OrganizationOut.model_validate(org)


@router.post("/{org_id}/approve", response_model=OrganizationOut)
async def approve_organization(
    org_id: uuid.UUID,
    data: OrganizationApprove,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    from models.organization import OrganizationStatus
    from datetime import datetime, timezone

    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.status = OrganizationStatus.APPROVED
    org.is_licensed = True
    org.approved_at = datetime.now(timezone.utc)
    org.approved_by_id = current_user.id
    org.notes = data.notes
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="org_approved",
        resource_type="pharmacy_organization",
        resource_id=org.id,
        actor_id=current_user.id,
        after_state={"status": "approved"},
        ip_address=request.client.host if request.client else None,
    )
    return OrganizationOut.model_validate(org)


@router.post("/{org_id}/reject", response_model=OrganizationOut)
async def reject_organization(
    org_id: uuid.UUID,
    data: OrganizationReject,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    from models.organization import OrganizationStatus
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.status = OrganizationStatus.REJECTED
    org.rejection_reason = data.reason
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="org_rejected",
        resource_type="pharmacy_organization",
        resource_id=org.id,
        actor_id=current_user.id,
        after_state={"status": "rejected", "reason": data.reason},
        ip_address=request.client.host if request.client else None,
    )
    return OrganizationOut.model_validate(org)


@router.post("/{org_id}/suspend", response_model=OrganizationOut)
async def suspend_organization(
    org_id: uuid.UUID,
    data: OrganizationSuspend,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    from models.organization import OrganizationStatus
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.status = OrganizationStatus.SUSPENDED
    org.suspension_reason = data.reason
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="org_suspended",
        resource_type="pharmacy_organization",
        resource_id=org.id,
        actor_id=current_user.id,
        after_state={"status": "suspended", "reason": data.reason},
        ip_address=request.client.host if request.client else None,
    )
    return OrganizationOut.model_validate(org)


# ── Compliance documents ─────────────────────────────────────────────────────
# Approval is meaningless without the paperwork behind it, so the CR extract and
# the pharmacy licence are uploaded here and read back by the admin reviewer.

_DOC_FIELDS = {"cr": "cr_doc_url", "license": "license_doc_url"}


async def _org_for_user(current_user, db) -> uuid.UUID:
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization")
    return org_id


@router.post("/me/documents/{doc_type}", response_model=OrganizationOut)
async def upload_my_document(
    doc_type: str,
    db: DbSession,
    current_user: OrgAdminOrAbove,
    request: Request,
    file: UploadFile = File(...),
):
    """Upload this organization's commercial registration or pharmacy licence."""
    from services.storage_service import storage_service

    field = _DOC_FIELDS.get(doc_type)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع المستند غير معروف — المسموح: cr أو license",
        )

    org_id = await _org_for_user(current_user, db)
    repo = OrganizationRepository(db)
    org = await repo.get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    stored = await storage_service.save_document(file, org_id, doc_type, db)
    setattr(org, field, stored)
    await db.flush()

    await AuditService(db).log(
        action="document_uploaded",
        resource_type="pharmacy_organization",
        resource_id=org.id,
        actor_id=current_user.id,
        organization_id=org.id,
        after_state={"document": doc_type},
        ip_address=request.client.host if request.client else None,
    )
    return OrganizationOut.model_validate(org)


@router.get("/{org_id}/documents/{doc_type}")
async def download_document(
    org_id: uuid.UUID,
    doc_type: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Readable by the owning organization and by platform admins — nobody else."""
    from services.storage_service import storage_service

    field = _DOC_FIELDS.get(doc_type)
    if not field:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع المستند غير معروف")

    if current_user.role != UserRole.SUPER_ADMIN:
        own_org = await MembershipRepository(db).get_user_org_id(current_user.id)
        if own_org != org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    org = await OrganizationRepository(db).get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    stored = getattr(org, field)
    if not stored:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="لم يرفع هذا المستند بعد")

    # Reads through to the durable copy, so a deploy that wiped the disk does
    # not turn an approved pharmacy's licence into "file not found".
    content, content_type = await storage_service.read(stored, db)
    suffix = Path(stored).suffix or ".pdf"
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{doc_type}-{org_id}{suffix}"'
        },
    )


@router.delete("/me/documents/{doc_type}", response_model=MessageResponse)
async def delete_my_document(
    doc_type: str,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    field = _DOC_FIELDS.get(doc_type)
    if not field:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="نوع المستند غير معروف")

    org_id = await _org_for_user(current_user, db)
    org = await OrganizationRepository(db).get_active(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    setattr(org, field, None)
    await db.flush()
    return MessageResponse(message="تم حذف المستند")
