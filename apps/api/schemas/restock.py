"""
Restock recommendation schemas.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.restock import EvidenceStrength, RecommendationStatus, RestockAction, RestockKind


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    branch_id: uuid.UUID
    product_id: uuid.UUID
    kind: RestockKind
    status: RecommendationStatus
    action: RestockAction
    batch_id: uuid.UUID | None = None
    evidence_strength: EvidenceStrength
    demand_window_days: int | None = None
    incoming_qty: int
    suggested_qty: int
    suggested_price: float | None = None
    days_of_cover: float | None = None
    daily_velocity: float
    on_hand_qty: int
    nearest_expiry_date: date | None = None
    expiry_zone: str
    market_median_price: float | None = None
    matched_listing_id: uuid.UUID | None = None
    inputs: dict | None = None
    reason_ar: str
    reason_en: str
    computed_at: datetime
    dismissed_at: datetime | None = None
    acted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    product_name: str | None = None
    product_name_ar: str | None = None
    product_sku: str | None = None
    branch_name: str | None = None


class RecommendationSummary(BaseModel):
    total: int
    counts: dict[str, int]
    last_computed_at: datetime | None = None


class RefreshResponse(BaseModel):
    created: int
    updated: int
    unchanged: int
    superseded: int
    new_listing_recommendations: int
    total: int


class ActRequest(BaseModel):
    action: Literal["open_listing", "create_listing"]
    asking_price: float | None = Field(None, gt=0)
    quantity: int | None = Field(None, ge=1)


class ActResponse(BaseModel):
    recommendation: RecommendationOut
    listing_id: uuid.UUID | None = None
