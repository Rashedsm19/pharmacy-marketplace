"""Restock router — recommendation listing, refresh, dismiss and act."""
from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from dependencies import CurrentUser, DbSession, require_permission
from models.user import User
from repositories.organization import MembershipRepository
from repositories.restock import RestockRecommendationRepository
from schemas.common import PaginatedResponse
from schemas.restock import (
    ActRequest,
    ActResponse,
    RecommendationOut,
    RecommendationSummary,
    RefreshResponse,
)
from services.entitlement_service import EntitlementService
from services.restock_service import RestockService

router = APIRouter(prefix="/restock", tags=["Restock"])

RestockViewer = Annotated[User, Depends(require_permission("restock.view"))]


async def _require_org(current_user, db) -> uuid.UUID:
    from models.user import UserRole
    if current_user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Use org_id param for super admin")
    mem_repo = MembershipRepository(db)
    org_id = await mem_repo.get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=403, detail="No organization")
    return org_id


async def _entitled_org(current_user, db) -> uuid.UUID:
    org_id = await _require_org(current_user, db)
    await EntitlementService(db).require_feature(org_id, "restock_intelligence")
    return org_id


def _to_out(rec) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        organization_id=rec.organization_id,
        branch_id=rec.branch_id,
        product_id=rec.product_id,
        kind=rec.kind,
        status=rec.status,
        action=rec.action,
        batch_id=rec.batch_id,
        evidence_strength=rec.evidence_strength,
        demand_window_days=rec.demand_window_days,
        incoming_qty=rec.incoming_qty,
        suggested_qty=rec.suggested_qty,
        suggested_price=float(rec.suggested_price) if rec.suggested_price is not None else None,
        days_of_cover=float(rec.days_of_cover) if rec.days_of_cover is not None else None,
        daily_velocity=float(rec.daily_velocity),
        on_hand_qty=rec.on_hand_qty,
        nearest_expiry_date=rec.nearest_expiry_date,
        expiry_zone=rec.expiry_zone,
        market_median_price=(
            float(rec.market_median_price) if rec.market_median_price is not None else None
        ),
        matched_listing_id=rec.matched_listing_id,
        inputs=rec.inputs,
        reason_ar=rec.reason_ar,
        reason_en=rec.reason_en,
        computed_at=rec.computed_at,
        dismissed_at=rec.dismissed_at,
        acted_at=rec.acted_at,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        product_name=rec.product.name if rec.product else None,
        product_name_ar=rec.product.name_ar if rec.product else None,
        product_sku=rec.product.sku if rec.product else None,
        branch_name=rec.branch.name if rec.branch else None,
    )


@router.get("/recommendations", response_model=PaginatedResponse[RecommendationOut])
async def list_recommendations(
    db: DbSession,
    current_user: RestockViewer,
    kind: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    branch_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
):
    org_id = await _entitled_org(current_user, db)
    from models.restock import RecommendationStatus, RestockKind

    kind_val = None
    if kind:
        try:
            kind_val = RestockKind(kind)
        except ValueError:
            raise HTTPException(status_code=400, detail="نوع التوصية غير معروف")
    status_val = None
    if status_filter:
        try:
            status_val = RecommendationStatus(status_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail="حالة التوصية غير معروفة")

    repo = RestockRecommendationRepository(db)
    rows, total = await repo.list_for_org(
        org_id,
        kind=kind_val,
        status=status_val,
        branch_id=branch_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return PaginatedResponse(
        items=[_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/recommendations/summary", response_model=RecommendationSummary)
async def recommendations_summary(
    db: DbSession,
    current_user: RestockViewer,
):
    org_id = await _entitled_org(current_user, db)
    repo = RestockRecommendationRepository(db)
    counts = await repo.counts_by_status(org_id)
    return RecommendationSummary(
        total=sum(counts.values()),
        counts=counts,
        last_computed_at=await repo.last_computed_at(org_id),
    )


@router.post("/recommendations/refresh", response_model=RefreshResponse)
async def refresh_recommendations(
    db: DbSession,
    current_user: RestockViewer,
):
    org_id = await _entitled_org(current_user, db)
    summary = await RestockService(db).compute_for_org(org_id)
    counts = await RestockRecommendationRepository(db).counts_by_status(org_id)
    return RefreshResponse(**summary, total=sum(counts.values()))


@router.get("/recommendations/{rec_id}", response_model=RecommendationOut)
async def get_recommendation(
    rec_id: uuid.UUID,
    db: DbSession,
    current_user: RestockViewer,
):
    org_id = await _entitled_org(current_user, db)
    rec = await RestockService(db).mark_viewed(org_id, rec_id, current_user.id)
    return _to_out(rec)


@router.post("/recommendations/{rec_id}/dismiss", response_model=RecommendationOut)
async def dismiss_recommendation(
    rec_id: uuid.UUID,
    db: DbSession,
    current_user: RestockViewer,
):
    org_id = await _entitled_org(current_user, db)
    rec = await RestockService(db).dismiss(org_id, rec_id, current_user.id)
    return _to_out(rec)


@router.post("/recommendations/{rec_id}/act", response_model=ActResponse)
async def act_on_recommendation(
    rec_id: uuid.UUID,
    data: ActRequest,
    request: Request,
    db: DbSession,
    current_user: RestockViewer,
):
    org_id = await _entitled_org(current_user, db)
    rec, listing_id = await RestockService(db).act(
        org_id,
        rec_id,
        action=data.action,
        actor_id=current_user.id,
        asking_price=data.asking_price,
        quantity=data.quantity,
        ip_address=request.client.host if request.client else None,
    )
    return ActResponse(recommendation=_to_out(rec), listing_id=listing_id)
