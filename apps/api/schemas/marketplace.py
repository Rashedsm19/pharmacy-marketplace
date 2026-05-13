"""
Marketplace listing, offer, and reservation schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.marketplace import ListingStatus, OfferStatus, ReservationStatus


class ListingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: uuid.UUID
    title: str
    title_ar: str | None = None
    description: str | None = None
    quantity_listed: int = Field(ge=1)
    asking_price: float = Field(gt=0)
    minimum_offer_price: float | None = None
    allow_offers: bool = True
    allow_partial_purchase: bool = False
    min_purchase_quantity: int = Field(ge=1, default=1)
    expires_at: datetime | None = None


class ListingCreate(ListingBase):
    seller_branch_id: uuid.UUID


class ListingUpdate(BaseModel):
    title: str | None = None
    title_ar: str | None = None
    description: str | None = None
    asking_price: float | None = Field(None, gt=0)
    minimum_offer_price: float | None = None
    allow_offers: bool | None = None
    allow_partial_purchase: bool | None = None
    min_purchase_quantity: int | None = Field(None, ge=1)
    expires_at: datetime | None = None
    status: ListingStatus | None = None


class ListingOut(ListingBase):
    id: uuid.UUID
    seller_organization_id: uuid.UUID
    seller_branch_id: uuid.UUID
    created_by_id: uuid.UUID
    quantity_available: int
    status: ListingStatus
    view_count: int
    is_featured: bool
    eligibility_passed: bool
    created_at: datetime
    updated_at: datetime


class EligibilityRuleResult(BaseModel):
    rule_number: int
    rule_name: str
    passed: bool
    reason: str | None = None


class EligibilityResult(BaseModel):
    all_passed: bool
    rules: list[EligibilityRuleResult]


class ListingDetail(ListingOut):
    eligibility_result_detail: EligibilityResult | None = None
    product_name: str | None = None
    product_name_ar: str | None = None
    product_sku: str | None = None
    batch_number: str | None = None
    expiry_date: str | None = None
    days_until_expiry: int | None = None
    expiry_zone: str | None = None
    seller_org_name: str | None = None
    seller_branch_name: str | None = None
    open_offers_count: int = 0


class OfferBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offered_price: float = Field(gt=0)
    quantity: int = Field(ge=1)
    message: str | None = None


class OfferCreate(OfferBase):
    listing_id: uuid.UUID


class OfferUpdate(BaseModel):
    seller_note: str | None = None


class OfferOut(OfferBase):
    id: uuid.UUID
    listing_id: uuid.UUID
    buyer_organization_id: uuid.UUID
    submitted_by_id: uuid.UUID
    status: OfferStatus
    seller_note: str | None = None
    expires_at: datetime | None = None
    responded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReservationCreate(BaseModel):
    listing_id: uuid.UUID
    offer_id: uuid.UUID | None = None
    quantity: int = Field(ge=1)
    agreed_price: float = Field(gt=0)
    notes: str | None = None


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    offer_id: uuid.UUID | None = None
    buyer_organization_id: uuid.UUID
    reserved_by_id: uuid.UUID
    quantity: int
    agreed_price: float
    status: ReservationStatus
    expires_at: datetime
    confirmed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
