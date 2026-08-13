"""Dispute schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.dispute import DisputeReason, DisputeStatus


class DisputeCreate(BaseModel):
    transaction_id: uuid.UUID
    reason: DisputeReason
    description: str = Field(min_length=10, max_length=2000)
    # Omit to dispute the whole shipment.
    disputed_quantity: int | None = Field(default=None, ge=1)


class DisputeRespond(BaseModel):
    response: str = Field(min_length=5, max_length=2000)


class DisputeResolve(BaseModel):
    outcome: DisputeStatus
    notes: str = Field(min_length=5, max_length=2000)


class DisputeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    raised_by_organization_id: uuid.UUID
    reason: DisputeReason
    status: DisputeStatus
    description: str
    disputed_quantity: int | None = None
    evidence_url: str | None = None
    seller_response: str | None = None
    seller_responded_at: datetime | None = None
    resolution_notes: str | None = None
    resolved_at: datetime | None = None
    refund_amount: float | None = None
    created_at: datetime
    updated_at: datetime

    # Labels so the tables can name the case without extra round trips.
    transaction_reference: str | None = None
    raised_by_org_name: str | None = None
    product_name_ar: str | None = None
