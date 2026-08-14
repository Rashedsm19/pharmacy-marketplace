"""
Inventory import — download the template, upload a file, follow the job.

The upload endpoint deliberately does almost nothing: it validates the file,
stores it, and records a queued job. The worker in `scheduler.py` does the work,
because a request that takes ten thousand rows to answer is a request that times
out.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from config import settings
from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from models.branch import PharmacyBranch
from models.import_job import ImportJob, ImportSource, ImportStatus
from models.user import UserRole
from repositories.organization import MembershipRepository
from schemas.import_job import ImportCapacity, ImportJobList, ImportJobOut
from services import excel_service
from services.audit_service import AuditService
from services.import_service import count_org_items
from services.storage_service import storage_service

router = APIRouter(prefix="/inventory/import", tags=["Inventory import"])

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


async def _org_or_none(current_user, db) -> uuid.UUID | None:
    """The caller's pharmacy, or None for a platform admin who has none."""
    if current_user.role == UserRole.SUPER_ADMIN:
        return None
    return await MembershipRepository(db).get_user_org_id(current_user.id)


async def _require_org(current_user, db) -> uuid.UUID:
    """For the endpoints that genuinely write into one pharmacy's stock."""
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الاستيراد يتم من حساب المنشأة، ومدير المنصة يتابعه من «عمليات الاستيراد»",
        )
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="لا توجد منشأة مرتبطة بالحساب"
        )
    return org_id


def _to_out(job: ImportJob) -> ImportJobOut:
    payload = ImportJobOut.model_validate(job)
    payload.has_error_file = bool(job.error_file_path)
    return payload


@router.get("/template")
async def download_template(current_user: CurrentUser, db: DbSession) -> Response:
    """The blank sheet, with this pharmacy's branches already in the dropdown.

    Deliberately available to anyone signed in, including a platform admin with
    no pharmacy of their own — the template is a blank form, and an admin has
    every reason to download one to send to a customer. Only the branch dropdown
    depends on having an organization.
    """
    from sqlalchemy import select

    org_id = await _org_or_none(current_user, db)
    branches = []
    if org_id is not None:
        branches = (
            await db.execute(
                select(PharmacyBranch).where(
                    PharmacyBranch.organization_id == org_id,
                    PharmacyBranch.deleted_at.is_(None),
                )
            )
        ).scalars().all()

    content = excel_service.build_template([b.name_ar or b.name for b in branches])
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="medsave-inventory-template.xlsx"'
        },
    )


@router.get("/capacity", response_model=ImportCapacity)
async def get_capacity(current_user: CurrentUser, db: DbSession) -> ImportCapacity:
    """How much room the pharmacy has left, and whether it can import at all.

    Answers rather than refuses for a caller without a pharmacy, so the screen
    can explain the situation instead of showing a failed request.
    """
    limit = settings.MAX_INVENTORY_ITEMS_PER_ORG
    org_id = await _org_or_none(current_user, db)
    if org_id is None:
        return ImportCapacity(used=0, limit=limit, remaining=0, can_import=False)

    used = await count_org_items(db, org_id)
    return ImportCapacity(
        used=used, limit=limit, remaining=max(limit - used, 0), can_import=True
    )


@router.post("", response_model=ImportJobOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_inventory(
    request: Request,
    current_user: OrgAdminOrAbove,
    db: DbSession,
    file: UploadFile = File(...),
) -> ImportJobOut:
    """Queue a file for import. Returns immediately with a job to poll."""
    org_id = await _require_org(current_user, db)

    used = await count_org_items(db, org_id)
    if used >= settings.MAX_INVENTORY_ITEMS_PER_ORG:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"بلغ مخزونك الحد الأقصى ({settings.MAX_INVENTORY_ITEMS_PER_ORG} صنف). "
                "احذف أصنافاً منتهية أو تواصل معنا لرفع الحد."
            ),
        )

    stored_path, size = await storage_service.save_import_file(file, org_id)
    filename = (file.filename or "inventory.xlsx")[:255]

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

    await AuditService(db).log(
        action="inventory.import.upload",
        resource_type="import_job",
        resource_id=job.id,
        actor_id=current_user.id,
        organization_id=org_id,
        after_state={"filename": filename, "size_bytes": size},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(job)
    return _to_out(job)


@router.get("", response_model=ImportJobList)
async def list_jobs(
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    page_size: int = 20,
) -> ImportJobList:
    from sqlalchemy import func, select

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    org_id = await _org_or_none(current_user, db)
    if org_id is None:
        # A platform admin has no imports of their own; theirs is /admin/imports.
        return ImportJobList(items=[], total=0, page=page, page_size=page_size)

    total = int(
        await db.scalar(
            select(func.count(ImportJob.id)).where(ImportJob.organization_id == org_id)
        )
        or 0
    )
    rows = (
        await db.execute(
            select(ImportJob)
            .where(ImportJob.organization_id == org_id)
            .order_by(ImportJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return ImportJobList(
        items=[_to_out(job) for job in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _get_job(db, job_id: uuid.UUID, current_user) -> ImportJob:
    from sqlalchemy import select

    job = (
        await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    ).scalar_one_or_none()

    # A job belonging to another pharmacy is not "forbidden", it is not found —
    # the id itself must not confirm that something exists.
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العملية غير موجودة")
    if current_user.role != UserRole.SUPER_ADMIN:
        org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
        if job.organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="العملية غير موجودة"
            )
    return job


@router.get("/{job_id}", response_model=ImportJobOut)
async def get_job(job_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> ImportJobOut:
    return _to_out(await _get_job(db, job_id, current_user))


@router.get("/{job_id}/errors")
async def download_errors(
    job_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Response:
    """The rejected rows as a sheet the customer can fix and re-upload."""
    job = await _get_job(db, job_id, current_user)
    if not job.errors and not job.error_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="لا توجد أخطاء في هذه العملية"
        )

    if job.error_file_path:
        try:
            content = storage_service.resolve(job.error_file_path).read_bytes()
        except HTTPException:
            # The file aged out of a container's disk; rebuild it from the row.
            content = excel_service.build_errors_workbook(list(job.errors or []))
    else:
        content = excel_service.build_errors_workbook(list(job.errors or []))

    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="import-errors-{job_id}.xlsx"'
        },
    )
