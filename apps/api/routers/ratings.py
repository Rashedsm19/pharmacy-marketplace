"""Ratings router — leave and read counterparty ratings."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from dependencies import CurrentUser, DbSession, OrgAdminOrAbove
from models.rating import Rating
from models.transaction import Transaction, TransactionStatus
from repositories.organization import MembershipRepository
from services.audit_service import AuditService

router = APIRouter(prefix="/ratings", tags=["Ratings"])


class RatingCreate(BaseModel):
    transaction_id: uuid.UUID
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    rated_organization_id: uuid.UUID
    score: int
    comment: str | None = None
    created_at: datetime
    rater_org_name: str | None = None


class OrgRatingSummary(BaseModel):
    organization_id: uuid.UUID
    average: float | None = None
    count: int


async def _org_id(current_user, db) -> uuid.UUID:
    org_id = await MembershipRepository(db).get_user_org_id(current_user.id)
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization")
    return org_id


@router.post("", response_model=RatingOut, status_code=201)
async def leave_rating(
    data: RatingCreate,
    db: DbSession,
    current_user: OrgAdminOrAbove,
):
    """Rate the other side of a completed transaction."""
    org_id = await _org_id(current_user, db)
    tx = (
        await db.execute(select(Transaction).where(Transaction.id == data.transaction_id))
    ).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="المعاملة غير موجودة")

    if org_id not in (tx.buyer_organization_id, tx.seller_organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مخول")

    # A rating has to be earned: nothing to judge before the goods arrive.
    if tx.status != TransactionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا يمكن التقييم قبل إتمام المعاملة",
        )

    existing = (
        await db.execute(
            select(Rating).where(
                Rating.transaction_id == data.transaction_id,
                Rating.rater_organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="سبق أن قيمت هذه المعاملة"
        )

    rated_org_id = (
        tx.seller_organization_id
        if org_id == tx.buyer_organization_id
        else tx.buyer_organization_id
    )
    rating = Rating(
        id=uuid.uuid4(),
        transaction_id=data.transaction_id,
        rater_organization_id=org_id,
        rated_organization_id=rated_org_id,
        rated_by_id=current_user.id,
        score=data.score,
        comment=data.comment,
    )
    db.add(rating)
    await db.flush()

    await AuditService(db).log(
        action="rating_left",
        resource_type="rating",
        resource_id=rating.id,
        actor_id=current_user.id,
        organization_id=org_id,
        after_state={"score": data.score, "rated_organization_id": rated_org_id},
    )
    return RatingOut.model_validate(rating)


@router.get("/organization/{org_id}", response_model=OrgRatingSummary)
async def organization_rating(org_id: uuid.UUID, db: DbSession, current_user: CurrentUser):
    """Average and count for one organization — shown on listings and profiles."""
    row = (
        await db.execute(
            select(func.avg(Rating.score), func.count(Rating.id)).where(
                Rating.rated_organization_id == org_id
            )
        )
    ).one()
    average, count = row
    return OrgRatingSummary(
        organization_id=org_id,
        average=round(float(average), 2) if average is not None else None,
        count=count,
    )


@router.get("/organization/{org_id}/list", response_model=list[RatingOut])
async def organization_ratings(
    org_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 20,
):
    rows = (
        await db.execute(
            select(Rating)
            .where(Rating.rated_organization_id == org_id)
            .order_by(Rating.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    out = []
    for row in rows:
        item = RatingOut.model_validate(row)
        if row.rater_organization is not None:
            item.rater_org_name = (
                row.rater_organization.name_ar or row.rater_organization.name
            )
        out.append(item)
    return out
