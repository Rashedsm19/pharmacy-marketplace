"""Admin router — approvals queue, moderation, settings, audit logs."""
from __future__ import annotations

import math
import uuid
from datetime import timedelta

from fastapi import APIRouter, Request
from sqlalchemy import select

from dependencies import DbSession, SuperAdmin
from schemas.admin import PromoteDraftIn
from models.organization import OrganizationStatus, PharmacyOrganization
from models.user import User
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
    actor_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
):
    repo = AuditLogRepository(db)
    rows, total = await repo.list_filtered(
        org_id=org_id, action=action, resource_type=resource_type, actor_id=actor_id,
        offset=(page - 1) * page_size, limit=page_size,
    )

    # Resolve actor / organization names in one pass — a bare UUID tells a human
    # reviewer nothing about who performed the action.
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    org_ids = {r.organization_id for r in rows if r.organization_id}
    actors: dict[uuid.UUID, User] = {}
    org_names: dict[uuid.UUID, str] = {}
    if actor_ids:
        result = await db.execute(select(User).where(User.id.in_(actor_ids)))
        actors = {u.id: u for u in result.scalars().all()}
    if org_ids:
        result = await db.execute(select(PharmacyOrganization).where(
            PharmacyOrganization.id.in_(org_ids)
        ))
        org_names = {o.id: (o.name_ar or o.name) for o in result.scalars().all()}

    return {
        "items": [
            {
                "id": str(r.id),
                "actor_id": str(r.actor_id) if r.actor_id else None,
                "user_email": actors[r.actor_id].email if r.actor_id in actors else None,
                "user_full_name": actors[r.actor_id].full_name if r.actor_id in actors else None,
                "user_org_name": org_names.get(r.organization_id),
                "organization_id": str(r.organization_id) if r.organization_id else None,
                "action": r.action,
                # `entity_*` mirrors `resource_*` for the admin audit screen
                "resource_type": r.resource_type,
                "entity_type": r.resource_type,
                "resource_id": str(r.resource_id) if r.resource_id else None,
                "entity_id": str(r.resource_id) if r.resource_id else None,
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
    """Platform settings, described well enough to be edited safely.

    The stored shape is a key and a JSON blob, which tells an administrator
    nothing — `marketplace.platform_fee_pct` with `{"value": 2}` does not say
    whether 2 is a percentage or an amount. Each row therefore comes back with
    its meaning in Arabic and English, its type, and its allowed range.
    """
    from sqlalchemy import select

    from models.settings import PlatformSettings
    from services.settings_catalog import describe, unwrap

    result = await db.execute(
        select(PlatformSettings).order_by(PlatformSettings.category, PlatformSettings.key)
    )
    return [
        {
            "id": str(s.id),
            "key": s.key,
            # Unwrapped, so a screen can render it instead of "[object Object]".
            "value": unwrap(s.value),
            "raw_value": s.value,
            "value_text": s.value_text,
            "description": s.description,
            "category": s.category,
            "updated_at": s.updated_at.isoformat(),
            **describe(s.key, s.value, s.description),
        }
        for s in result.scalars().all()
    ]


@router.put("/settings/{key}")
async def upsert_setting(
    key: str,
    value: dict,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    from fastapi import HTTPException, status as http_status
    from sqlalchemy import select

    from models.settings import PlatformSettings
    from services.audit_service import AuditService
    from services.settings_catalog import coerce, unwrap

    # The form submits text; store the type the setting is meant to hold, or a
    # percentage silently becomes the string "2" and every later comparison
    # against it is wrong.
    try:
        submitted = coerce(key, value.get("value"))
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    # Always the wrapped shape, matching what the seed writes — the two used to
    # disagree, so a seeded row and an edited row were stored differently.
    stored = {"value": submitted}

    result = await db.execute(select(PlatformSettings).where(PlatformSettings.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        before = {"value": unwrap(setting.value)}
        setting.value = stored
        if value.get("value_text") is not None:
            setting.value_text = value.get("value_text")
        setting.updated_by_id = current_user.id
    else:
        setting = PlatformSettings(
            id=uuid.uuid4(),
            key=key,
            value=stored,
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
        after_state={"key": key, "value": submitted},
        ip_address=request.client.host if request.client else None,
    )

    return {"id": str(setting.id), "key": setting.key, "value": submitted}


# ── Cross-pharmacy visibility ─────────────────────────────────────────────────
#
# Everything above this line is org-scoped by design: a pharmacy sees only its
# own stock, and that isolation is enforced in every repository. These three
# views are the deliberate exception, gated on SuperAdmin, because someone has to
# be able to see the platform as a whole — what is held, what is expiring, what
# customers are importing, and which private products should join the catalogue.


def _zone(days: int) -> str:
    if days < 30:
        return "red"
    if days < 90:
        return "orange"
    if days <= 180:
        return "yellow"
    return "green"


@router.get("/inventory")
async def list_all_inventory(
    db: DbSession,
    current_user: SuperAdmin,
    organization_id: uuid.UUID | None = None,
    zone: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """Every batch on the platform, with the pharmacy that holds it."""
    from datetime import date

    from sqlalchemy import func, or_

    from models.branch import PharmacyBranch
    from models.inventory import InventoryBatch
    from models.product import Product
    from schemas.admin import AdminBatchRow, AdminInventoryOut, AdminInventoryTotals

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    today = date.today()

    conditions = [InventoryBatch.deleted_at.is_(None)]
    if organization_id:
        conditions.append(InventoryBatch.organization_id == organization_id)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Product.name.ilike(pattern),
                Product.name_ar.ilike(pattern),
                Product.sku.ilike(pattern),
                InventoryBatch.batch_number.ilike(pattern),
            )
        )
    # Zone is a date range, so it filters in SQL rather than after paging —
    # otherwise "show me the red ones" would only search the current page.
    # The bounds must match _zone() exactly, or a filtered page shows rows
    # labelled with a different band than the one asked for.
    if zone:
        day = lambda n: today + timedelta(days=n)  # noqa: E731
        if zone == "expired":
            conditions.append(InventoryBatch.expiry_date <= today)
        elif zone == "red":
            conditions.append(InventoryBatch.expiry_date > today)
            conditions.append(InventoryBatch.expiry_date < day(30))
        elif zone == "orange":
            conditions.append(InventoryBatch.expiry_date >= day(30))
            conditions.append(InventoryBatch.expiry_date < day(90))
        elif zone == "yellow":
            conditions.append(InventoryBatch.expiry_date >= day(90))
            conditions.append(InventoryBatch.expiry_date <= day(180))
        elif zone == "green":
            conditions.append(InventoryBatch.expiry_date > day(180))

    base = (
        select(InventoryBatch, Product, PharmacyBranch, PharmacyOrganization)
        .join(Product, Product.id == InventoryBatch.product_id)
        .join(PharmacyBranch, PharmacyBranch.id == InventoryBatch.branch_id)
        .join(
            PharmacyOrganization,
            PharmacyOrganization.id == InventoryBatch.organization_id,
        )
        .where(*conditions)
    )

    total = int(
        await db.scalar(
            select(func.count())
            .select_from(InventoryBatch)
            .join(Product, Product.id == InventoryBatch.product_id)
            .where(*conditions)
        )
        or 0
    )

    rows = (
        await db.execute(
            base.order_by(InventoryBatch.expiry_date)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = []
    for batch, product, branch, organization in rows:
        days = (batch.expiry_date - today).days
        items.append(
            AdminBatchRow(
                id=batch.id,
                organization_id=organization.id,
                organization_name=organization.name_ar or organization.name,
                branch_name=branch.name_ar or branch.name,
                product_name=product.name_ar or product.name,
                product_sku=product.sku,
                is_draft_product=bool(product.is_draft),
                product_source=str(getattr(product.source, "value", product.source)),
                batch_number=batch.batch_number,
                expiry_date=batch.expiry_date,
                days_remaining=days,
                quantity=batch.quantity,
                quantity_available=batch.quantity_available,
                unit_cost=float(batch.unit_cost) if batch.unit_cost is not None else None,
                status=str(getattr(batch.status, "value", batch.status)),
                zone="expired" if days <= 0 else _zone(days),
                created_at=batch.created_at,
            )
        )

    # Totals cover the whole platform, not the page — the page is a window.
    summary = (
        await db.execute(
            select(
                func.count(func.distinct(InventoryBatch.organization_id)),
                func.count(InventoryBatch.id),
                func.coalesce(func.sum(InventoryBatch.quantity_available), 0),
                func.coalesce(
                    func.sum(
                        InventoryBatch.quantity_available * InventoryBatch.unit_cost
                    ),
                    0,
                ),
            ).where(InventoryBatch.deleted_at.is_(None))
        )
    ).one()

    near_expiry = int(
        await db.scalar(
            select(func.count(InventoryBatch.id)).where(
                InventoryBatch.deleted_at.is_(None),
                InventoryBatch.expiry_date > today,
                InventoryBatch.expiry_date <= today + timedelta(days=180),
            )
        )
        or 0
    )
    expired = int(
        await db.scalar(
            select(func.count(InventoryBatch.id)).where(
                InventoryBatch.deleted_at.is_(None),
                InventoryBatch.expiry_date <= today,
            )
        )
        or 0
    )

    return AdminInventoryOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
        totals=AdminInventoryTotals(
            organizations=int(summary[0] or 0),
            batches=int(summary[1] or 0),
            units=int(summary[2] or 0),
            estimated_value=float(summary[3] or 0),
            near_expiry_batches=near_expiry,
            expired_batches=expired,
        ),
    )


@router.get("/products/drafts")
async def list_draft_products(
    db: DbSession,
    current_user: SuperAdmin,
    organization_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """Private products an import created, awaiting review for the catalogue."""
    from sqlalchemy import func

    from models.inventory import InventoryBatch
    from models.product import Product, ProductCategory
    from schemas.admin import AdminDraftList, AdminDraftProduct

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    conditions = [Product.is_draft.is_(True), Product.deleted_at.is_(None)]
    if organization_id:
        conditions.append(Product.owner_organization_id == organization_id)

    batch_counts = (
        select(
            InventoryBatch.product_id,
            func.count(InventoryBatch.id).label("batches"),
        )
        .where(InventoryBatch.deleted_at.is_(None))
        .group_by(InventoryBatch.product_id)
        .subquery()
    )

    total = int(
        await db.scalar(select(func.count(Product.id)).where(*conditions)) or 0
    )
    rows = (
        await db.execute(
            select(
                Product,
                PharmacyOrganization,
                ProductCategory,
                batch_counts.c.batches,
            )
            .outerjoin(
                PharmacyOrganization,
                PharmacyOrganization.id == Product.owner_organization_id,
            )
            .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
            .outerjoin(batch_counts, batch_counts.c.product_id == Product.id)
            .where(*conditions)
            .order_by(Product.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return AdminDraftList(
        items=[
            AdminDraftProduct(
                id=product.id,
                organization_id=product.owner_organization_id,
                organization_name=(organization.name_ar or organization.name)
                if organization
                else None,
                name=product.name,
                name_ar=product.name_ar,
                sku=product.sku,
                barcode=product.barcode,
                category_name=(category.name_ar or category.name) if category else None,
                source=str(getattr(product.source, "value", product.source)),
                batch_count=int(batches or 0),
                created_at=product.created_at,
            )
            for product, organization, category, batches in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/products/drafts/{product_id}/promote")
async def promote_draft_product(
    product_id: uuid.UUID,
    payload: PromoteDraftIn,
    db: DbSession,
    current_user: SuperAdmin,
    request: Request,
):
    """Move a private product into the catalogue every pharmacy shares.

    The batches already pointing at it keep pointing at it, so the pharmacy's
    stock is untouched — what changes is that the product stops being private.
    """
    from fastapi import HTTPException, status as http_status
    from sqlalchemy.exc import IntegrityError

    from models.product import Product, ProductSource
    from services.audit_service import AuditService

    product = (
        await db.execute(
            select(Product).where(
                Product.id == product_id, Product.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="المنتج غير موجود"
        )
    if not product.is_draft:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="هذا المنتج ليس مسودة",
        )

    before = {
        "owner_organization_id": str(product.owner_organization_id),
        "sku": product.sku,
        "is_draft": True,
    }

    if payload.name:
        product.name = payload.name[:255]
    if payload.name_ar:
        product.name_ar = payload.name_ar[:255]
    if payload.sku:
        product.sku = payload.sku[:100]
    if payload.barcode is not None:
        product.barcode = payload.barcode[:100] or None
    if payload.category_id:
        product.category_id = payload.category_id

    product.owner_organization_id = None
    product.is_draft = False
    product.source = ProductSource.CATALOG

    # Read the code before flushing: a rollback expires the instance, and
    # touching an attribute afterwards would attempt IO outside the session.
    attempted_sku = product.sku

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # The catalogue already holds this code; the admin must supply another.
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"الكود {attempted_sku} مستخدم في الكتالوج العام — اختر كوداً آخر",
        ) from None

    await AuditService(db).log(
        action="admin.product.promote_draft",
        resource_type="product",
        resource_id=product.id,
        actor_id=current_user.id,
        before_state=before,
        after_state={"sku": product.sku, "is_draft": False},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {
        "id": str(product.id),
        "sku": product.sku,
        "name": product.name,
        "is_draft": product.is_draft,
        "owner_organization_id": None,
    }


@router.get("/imports")
async def list_all_imports(
    db: DbSession,
    current_user: SuperAdmin,
    organization_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """Every import on the platform — uploaded files and API syncs alike."""
    from sqlalchemy import func

    from models.import_job import ImportJob
    from schemas.admin import AdminImportList, AdminImportRow

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    conditions = []
    if organization_id:
        conditions.append(ImportJob.organization_id == organization_id)
    if status_filter:
        conditions.append(ImportJob.status == status_filter)

    total = int(
        await db.scalar(select(func.count(ImportJob.id)).where(*conditions)) or 0
    )
    rows = (
        await db.execute(
            select(ImportJob, PharmacyOrganization, User)
            .join(
                PharmacyOrganization,
                PharmacyOrganization.id == ImportJob.organization_id,
            )
            .outerjoin(User, User.id == ImportJob.created_by_id)
            .where(*conditions)
            .order_by(ImportJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return AdminImportList(
        items=[
            AdminImportRow(
                id=job.id,
                organization_id=organization.id,
                organization_name=organization.name_ar or organization.name,
                created_by_name=user.full_name if user else None,
                filename=job.filename,
                source=str(getattr(job.source, "value", job.source)),
                status=str(getattr(job.status, "value", job.status)),
                total_rows=job.total_rows,
                processed_rows=job.processed_rows,
                created_batches=job.created_batches,
                updated_batches=job.updated_batches,
                created_products=job.created_products,
                failed_rows=job.failed_rows,
                failure_reason=job.failure_reason,
                started_at=job.started_at,
                finished_at=job.finished_at,
                created_at=job.created_at,
            )
            for job, organization, user in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )
